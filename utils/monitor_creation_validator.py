#!/usr/bin/env python3
"""
Monitor Creation Validation System

This module provides comprehensive validation for Enhanced TP/SL monitor creation
to prevent partial failures and ensure atomic monitor operations.
"""

import asyncio
import pickle
import time
import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MonitorValidationResult:
    """Result of monitor creation validation"""
    success: bool
    monitor_key: str
    account_type: str
    errors: List[str]
    warnings: List[str]
    created_at: float

class MonitorCreationValidator:
    """
    Comprehensive validation system for Enhanced TP/SL monitor creation

    Features:
    - Atomic monitor creation (all-or-nothing)
    - Persistence validation
    - Runtime validation
    - Recovery mechanisms
    - Health checks
    """

    def __init__(self, pickle_path: str = None):
        self.pickle_path = pickle_path or '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.validation_results = {}

    async def validate_monitor_creation_requirements(
        self,
        symbol: str,
        side: str,
        account_type: str,
        position_data: Dict[str, Any],
        tp_orders: List[Dict],
        sl_order: Dict
    ) -> MonitorValidationResult:
        """
        Validate all requirements for monitor creation before attempting creation
        """

        monitor_key = f"{symbol}_{side}" + ("_MIRROR" if account_type == "mirror" else "")
        errors = []
        warnings = []

        logger.info(f"🔍 Validating monitor creation requirements for {monitor_key}")

        # Validate symbol and side
        if not symbol or len(symbol) < 3:
            errors.append(f"Invalid symbol: {symbol}")

        if side not in ['Buy', 'Sell']:
            errors.append(f"Invalid side: {side}")

        if account_type not in ['main', 'mirror']:
            errors.append(f"Invalid account type: {account_type}")

        # Validate position data
        required_position_fields = ['size', 'avg_price', 'position_idx']
        for field in required_position_fields:
            if field not in position_data:
                errors.append(f"Missing position field: {field}")
            elif position_data[field] is None:
                errors.append(f"Null position field: {field}")

        # Validate position size
        try:
            position_size = Decimal(str(position_data.get('size', 0)))
            if position_size <= 0:
                errors.append(f"Invalid position size: {position_size}")
        except (ValueError, TypeError):
            errors.append(f"Invalid position size format: {position_data.get('size')}")

        # Validate TP orders
        if not tp_orders:
            warnings.append("No TP orders provided")
        else:
            for i, tp_order in enumerate(tp_orders):
                required_tp_fields = ['order_id', 'price', 'quantity']
                for field in required_tp_fields:
                    if field not in tp_order:
                        errors.append(f"TP{i+1} missing field: {field}")

                try:
                    price = Decimal(str(tp_order.get('price', 0)))
                    quantity = Decimal(str(tp_order.get('quantity', 0)))
                    if price <= 0 or quantity <= 0:
                        errors.append(f"TP{i+1} invalid price/quantity: {price}/{quantity}")
                except (ValueError, TypeError):
                    errors.append(f"TP{i+1} invalid price/quantity format")

        # Validate SL order
        if not sl_order:
            warnings.append("No SL order provided")
        else:
            required_sl_fields = ['order_id', 'price', 'quantity']
            for field in required_sl_fields:
                if field not in sl_order:
                    errors.append(f"SL missing field: {field}")

            try:
                sl_price = Decimal(str(sl_order.get('price', 0)))
                sl_quantity = Decimal(str(sl_order.get('quantity', 0)))
                if sl_price <= 0 or sl_quantity <= 0:
                    errors.append(f"SL invalid price/quantity: {sl_price}/{sl_quantity}")
            except (ValueError, TypeError):
                errors.append(f"SL invalid price/quantity format")

        # Check for existing monitor conflicts
        try:
            existing_monitors = await self._get_existing_monitors()
            if monitor_key in existing_monitors:
                warnings.append(f"Monitor {monitor_key} already exists - will be overwritten")
        except Exception as e:
            warnings.append(f"Could not check existing monitors: {e}")

        success = len(errors) == 0

        result = MonitorValidationResult(
            success=success,
            monitor_key=monitor_key,
            account_type=account_type,
            errors=errors,
            warnings=warnings,
            created_at=time.time()
        )

        self.validation_results[monitor_key] = result

        if success:
            logger.info(f"✅ Validation passed for {monitor_key}")
            if warnings:
                for warning in warnings:
                    logger.warning(f"⚠️  {warning}")
        else:
            logger.error(f"❌ Validation failed for {monitor_key}")
            for error in errors:
                logger.error(f"   - {error}")

        return result

    async def create_monitor_atomically(
        self,
        validation_result: MonitorValidationResult,
        position_data: Dict[str, Any],
        tp_orders: List[Dict],
        sl_order: Dict,
        approach: str = "conservative"
    ) -> bool:
        """
        Create Enhanced TP/SL monitor atomically with full rollback on failure
        """

        if not validation_result.success:
            logger.error(f"❌ Cannot create monitor - validation failed for {validation_result.monitor_key}")
            return False

        monitor_key = validation_result.monitor_key
        logger.info(f"🔧 Creating monitor atomically: {monitor_key}")

        # Create backup before any changes
        backup_path = f"{self.pickle_path}.backup_atomic_{int(time.time())}"

        try:
            # Step 1: Create backup
            with open(self.pickle_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())

            # Step 2: Load current data
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)

            original_enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {}).copy()
            original_dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {}).copy()

            # Step 3: Create Enhanced TP/SL monitor
            enhanced_monitor = await self._create_enhanced_monitor(
                monitor_key, validation_result.account_type, position_data, tp_orders, sl_order, approach
            )

            # Step 4: Create Dashboard monitor
            dashboard_monitor = await self._create_dashboard_monitor(
                monitor_key, validation_result.account_type, position_data, approach
            )

            # Step 5: Atomic update
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})

            enhanced_monitors[monitor_key] = enhanced_monitor

            # Create dashboard monitor key based on approach
            if validation_result.account_type == 'main':
                # Extract chat_id from existing dashboard monitors
                chat_id = '5634913742'  # Default chat ID
                for key in dashboard_monitors.keys():
                    if key.startswith('5634913742_'):
                        chat_id = key.split('_')[0]
                        break

                dashboard_key = f"{chat_id}_{position_data['symbol']}_{approach}"
                dashboard_monitors[dashboard_key] = dashboard_monitor

            # Step 6: Save atomically
            with open(self.pickle_path, 'wb') as f:
                pickle.dump(data, f)

            # Step 7: Validate creation
            validation_success = await self._validate_monitor_persistence(monitor_key)

            if not validation_success:
                # Rollback on validation failure
                logger.error(f"❌ Monitor persistence validation failed for {monitor_key} - rolling back")

                # Restore from backup
                with open(backup_path, 'rb') as src, open(self.pickle_path, 'wb') as dst:
                    dst.write(src.read())

                return False

            # Step 8: Create reload signal
            signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
            with open(signal_file, 'w') as f:
                f.write(f"Atomic monitor creation: {monitor_key} at {time.time()}")

            logger.info(f"✅ Monitor created atomically: {monitor_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Atomic monitor creation failed for {monitor_key}: {e}")

            # Rollback on any exception
            try:
                with open(backup_path, 'rb') as src, open(self.pickle_path, 'wb') as dst:
                    dst.write(src.read())
                logger.info(f"✅ Successfully rolled back changes for {monitor_key}")
            except Exception as rollback_error:
                logger.error(f"❌ CRITICAL: Rollback failed for {monitor_key}: {rollback_error}")

            return False

    async def _create_enhanced_monitor(
        self,
        monitor_key: str,
        account_type: str,
        position_data: Dict[str, Any],
        tp_orders: List[Dict],
        sl_order: Dict,
        approach: str
    ) -> Dict[str, Any]:
        """Create Enhanced TP/SL monitor data structure"""

        monitor = {
            'symbol': position_data['symbol'],
            'side': position_data['side'],
            'position_size': Decimal(str(position_data['size'])),
            'current_size': Decimal(str(position_data['size'])),
            'remaining_size': Decimal(str(position_data['size'])),
            'entry_price': Decimal(str(position_data['avg_price'])),
            'position_idx': position_data.get('position_idx', 0),
            'unrealized_pnl': Decimal(str(position_data.get('unrealized_pnl', 0))),
            'approach': approach,
            'account_type': account_type,
            'monitor_type': 'enhanced_tp_sl',
            'created_at': time.time(),
            'last_check': time.time(),
            'last_update': time.time(),
            'circuit_breaker_count': 0,
            'is_active': True,
            'validation_passed': True,
            'atomic_creation': True,
            'tp_orders': [],
            'sl_order': {}
        }

        # Add TP orders
        tp_orders_data = []
        for tp_order in tp_orders:
            tp_orders_data.append({
                'order_id': tp_order.get('order_id', ''),
                'order_link_id': tp_order.get('order_link_id', ''),
                'price': Decimal(str(tp_order.get('price', 0))),
                'quantity': Decimal(str(tp_order.get('quantity', 0))),
                'original_quantity': Decimal(str(tp_order.get('quantity', 0))),
                'tp_number': tp_order.get('tp_number', 1),
                'status': tp_order.get('status', 'ACTIVE')
            })

        monitor['tp_orders'] = tp_orders_data

        # Add SL order
        if sl_order:
            monitor['sl_order'] = {
                'order_id': sl_order.get('order_id', ''),
                'order_link_id': sl_order.get('order_link_id', ''),
                'price': Decimal(str(sl_order.get('price', 0))),
                'quantity': Decimal(str(sl_order.get('quantity', 0))),
                'original_quantity': Decimal(str(sl_order.get('quantity', 0))),
                'status': sl_order.get('status', 'ACTIVE')
            }

        # Mirror account specific fields
        if account_type == 'mirror':
            monitor['mirror_account'] = True
            monitor['mirror_ratio'] = Decimal('0.6')

        return monitor

    async def _create_dashboard_monitor(
        self,
        monitor_key: str,
        account_type: str,
        position_data: Dict[str, Any],
        approach: str
    ) -> Dict[str, Any]:
        """Create Dashboard monitor data structure"""

        return {
            'symbol': position_data['symbol'],
            'side': position_data['side'],
            'approach': approach,
            'account_type': account_type,
            'monitor_key': monitor_key,
            'created_at': time.time(),
            'last_update': time.time(),
            'is_active': True,
            'validation_passed': True,
            'atomic_creation': True
        }

    async def _get_existing_monitors(self) -> Dict[str, Any]:
        """Get existing Enhanced TP/SL monitors"""

        try:
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)

            return data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        except Exception as e:
            logger.error(f"Error reading existing monitors: {e}")
            return {}

    async def _validate_monitor_persistence(self, monitor_key: str) -> bool:
        """Validate that monitor was properly persisted"""

        try:
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)

            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})

            if monitor_key not in enhanced_monitors:
                logger.error(f"❌ Monitor {monitor_key} not found in persistence")
                return False

            monitor = enhanced_monitors[monitor_key]

            # Validate critical fields
            required_fields = ['symbol', 'side', 'position_size', 'tp_orders', 'sl_order']
            for field in required_fields:
                if field not in monitor:
                    logger.error(f"❌ Monitor {monitor_key} missing required field: {field}")
                    return False

            # Validate data integrity
            if not monitor.get('tp_orders') and not monitor.get('sl_order'):
                logger.error(f"❌ Monitor {monitor_key} has no TP or SL orders")
                return False

            logger.info(f"✅ Monitor persistence validated: {monitor_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Error validating monitor persistence for {monitor_key}: {e}")
            return False

    async def verify_monitor_health(self) -> Dict[str, Any]:
        """Comprehensive monitor health check"""

        logger.info("🏥 Running comprehensive monitor health check")

        try:
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)

            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})

            health_report = {
                'total_enhanced_monitors': len(enhanced_monitors),
                'total_dashboard_monitors': len(dashboard_monitors),
                'healthy_monitors': 0,
                'unhealthy_monitors': 0,
                'missing_components': [],
                'errors': []
            }

            for monitor_key, monitor in enhanced_monitors.items():
                is_healthy = True

                # Check required fields
                required_fields = ['symbol', 'side', 'position_size', 'account_type']
                for field in required_fields:
                    if field not in monitor:
                        health_report['errors'].append(f"{monitor_key} missing {field}")
                        is_healthy = False

                # Check TP/SL orders
                tp_orders = monitor.get('tp_orders', [])
                sl_order = monitor.get('sl_order', {})

                if not tp_orders and not sl_order:
                    health_report['errors'].append(f"{monitor_key} has no TP or SL orders")
                    is_healthy = False

                if is_healthy:
                    health_report['healthy_monitors'] += 1
                else:
                    health_report['unhealthy_monitors'] += 1

            logger.info(f"📊 Monitor health: {health_report['healthy_monitors']} healthy, {health_report['unhealthy_monitors']} unhealthy")

            return health_report

        except Exception as e:
            logger.error(f"❌ Monitor health check failed: {e}")
            return {'error': str(e)}

# Singleton instance
monitor_validator = MonitorCreationValidator()