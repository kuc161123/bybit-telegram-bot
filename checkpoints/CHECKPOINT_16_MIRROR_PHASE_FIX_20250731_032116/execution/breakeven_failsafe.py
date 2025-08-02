#!/usr/bin/env python3
"""
Enhanced TP/SL Emergency Protection System
Provides comprehensive failsafe mechanisms for breakeven operations and SL protection
"""
import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from clients.bybit_helpers import (
    place_order_with_retry, cancel_order_with_retry, amend_order_with_retry,
    get_position_info, get_open_orders, get_current_price, get_correct_position_idx
)
from config.settings import (
    BREAKEVEN_SAFETY_MARGIN, DYNAMIC_FEE_CALCULATION,
    API_RETRY_MAX_ATTEMPTS, API_RETRY_INITIAL_DELAY
)
from utils.alert_helpers import send_simple_alert

logger = logging.getLogger(__name__)

class BreakevenMethod(Enum):
    """Different methods for moving SL to breakeven"""
    AMEND_FIRST = "amend_first"           # Try to amend existing order first
    CANCEL_REPLACE = "cancel_replace"     # Cancel and place new order
    EMERGENCY_MANUAL = "emergency_manual" # Manual market order placement
    PROGRESSIVE_RETRY = "progressive_retry" # Multiple attempts with different prices

class ProtectionStatus(Enum):
    """Status of position protection"""
    PROTECTED = "protected"               # SL is active and verified
    UNPROTECTED = "unprotected"          # No SL protection
    PARTIALLY_PROTECTED = "partial"      # SL exists but may be inadequate
    VERIFICATION_FAILED = "verification_failed"  # Cannot verify protection status
    EMERGENCY_MODE = "emergency_mode"    # Manual protection mode activated

@dataclass
class BreakevenAttempt:
    """Record of a breakeven attempt"""
    method: BreakevenMethod
    timestamp: float
    success: bool
    error_message: Optional[str] = None
    original_sl_price: Optional[Decimal] = None
    target_breakeven_price: Optional[Decimal] = None
    new_order_id: Optional[str] = None

@dataclass
class ProtectionState:
    """Current protection state of a position"""
    symbol: str
    side: str
    status: ProtectionStatus
    sl_order_id: Optional[str] = None
    sl_price: Optional[Decimal] = None
    last_verified: float = 0
    verification_attempts: int = 0
    emergency_mode: bool = False

class BreakevenFailsafeManager:
    """
    Comprehensive failsafe manager for breakeven operations and SL protection
    Implements multiple layers of protection to ensure positions never lose SL coverage
    """

    def __init__(self):
        self.protection_states: Dict[str, ProtectionState] = {}  # position_key -> state
        self.breakeven_attempts: Dict[str, List[BreakevenAttempt]] = {}  # position_key -> attempts
        self.emergency_locks: Dict[str, asyncio.Lock] = {}  # position_key -> lock
        self.verification_tasks: Dict[str, asyncio.Task] = {}  # position_key -> verification task

        # Configuration
        self.max_breakeven_attempts = 5
        self.emergency_sl_offset_percent = Decimal("0.002")  # 0.2% emergency offset
        self.verification_interval = 30  # seconds
        self.max_verification_failures = 3

        # Fallback configurations
        self.breakeven_price_adjustments = [
            Decimal("0.0006"),  # 0.06% (standard)
            Decimal("0.0008"),  # 0.08% (slightly higher)
            Decimal("0.0010"),  # 0.10% (conservative)
            Decimal("0.0012"),  # 0.12% (very conservative)
        ]

    async def move_sl_to_breakeven_atomic(
        self,
        monitor_data: Dict,
        entry_price: Decimal,
        current_price: Decimal
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Atomic breakeven operation with comprehensive failsafe mechanisms

        Returns:
            Tuple[success, message, new_sl_data]
        """
        symbol = monitor_data["symbol"]
        side = monitor_data["side"]
        position_key = f"{symbol}_{side}"
        chat_id = monitor_data["chat_id"]

        # Initialize protection state if not exists
        if position_key not in self.protection_states:
            self.protection_states[position_key] = ProtectionState(
                symbol=symbol,
                side=side,
                status=ProtectionStatus.PROTECTED,
                sl_order_id=monitor_data.get("sl_order", {}).get("order_id"),
                sl_price=monitor_data.get("sl_order", {}).get("price")
            )

        # Get or create emergency lock
        if position_key not in self.emergency_locks:
            self.emergency_locks[position_key] = asyncio.Lock()

        async with self.emergency_locks[position_key]:
            logger.info(f"🔒 Starting atomic breakeven operation for {position_key}")

            # Layer 1: Amend-First Approach
            success, message, sl_data = await self._try_amend_approach(
                monitor_data, entry_price, current_price
            )
            if success:
                await self._record_success(position_key, BreakevenMethod.AMEND_FIRST, sl_data)
                await self._send_breakeven_success_alert(monitor_data, sl_data, "Amend Method")
                return True, message, sl_data

            logger.warning(f"⚠️ Amend approach failed for {position_key}: {message}")

            # Layer 2: Atomic Cancel/Replace with Rollback
            success, message, sl_data = await self._try_atomic_cancel_replace(
                monitor_data, entry_price, current_price
            )
            if success:
                await self._record_success(position_key, BreakevenMethod.CANCEL_REPLACE, sl_data)
                await self._send_breakeven_success_alert(monitor_data, sl_data, "Cancel/Replace Method")
                return True, message, sl_data

            logger.warning(f"⚠️ Atomic cancel/replace failed for {position_key}: {message}")

            # Layer 3: Progressive Retry with Price Adjustments
            success, message, sl_data = await self._try_progressive_retry(
                monitor_data, entry_price, current_price
            )
            if success:
                await self._record_success(position_key, BreakevenMethod.PROGRESSIVE_RETRY, sl_data)
                await self._send_breakeven_success_alert(monitor_data, sl_data, "Progressive Retry Method")
                return True, message, sl_data

            logger.error(f"❌ Progressive retry failed for {position_key}: {message}")

            # Layer 4: Emergency Manual Protection
            success, message, sl_data = await self._activate_emergency_protection(
                monitor_data, entry_price, current_price
            )
            if success:
                await self._record_success(position_key, BreakevenMethod.EMERGENCY_MANUAL, sl_data)
                await self._send_emergency_protection_alert(monitor_data, sl_data)
                return True, message, sl_data

            # Complete failure - send critical alert
            await self._handle_complete_failure(monitor_data, chat_id)
            return False, "All breakeven methods failed - position unprotected", None

    async def _try_amend_approach(
        self,
        monitor_data: Dict,
        entry_price: Decimal,
        current_price: Decimal
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Try to amend existing SL order to breakeven price"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            sl_order = monitor_data.get("sl_order", {})

            if not sl_order or not sl_order.get("order_id"):
                return False, "No existing SL order to amend", None

            # Calculate breakeven price
            breakeven_price = self._calculate_breakeven_price(entry_price, side, 0)
            current_sl_price = sl_order.get("price")

            # Check if amendment is beneficial
            if not self._is_breakeven_beneficial(current_sl_price, breakeven_price, side):
                return False, f"Breakeven price {breakeven_price} not better than current SL {current_sl_price}", None

            logger.info(f"🔄 Attempting to amend SL order {sl_order['order_id'][:8]}... to breakeven price {breakeven_price}")

            # Attempt to amend the order
            amend_result = await amend_order_with_retry(
                symbol=symbol,
                order_id=sl_order["order_id"],
                trigger_price=str(breakeven_price),
                max_retries=3
            )

            if amend_result and amend_result.get("retCode") == 0:
                # Verify the amendment worked
                await asyncio.sleep(1)  # Brief delay for order update
                verification_success = await self._verify_sl_order(symbol, sl_order["order_id"], breakeven_price)

                if verification_success:
                    new_sl_data = {
                        "order_id": sl_order["order_id"],
                        "price": breakeven_price,
                        "order_link_id": sl_order.get("order_link_id", "") + "_BE_AMEND",
                        "method": "amend"
                    }
                    logger.info(f"✅ Successfully amended SL to breakeven via amend method")
                    return True, "SL amended to breakeven successfully", new_sl_data
                else:
                    logger.warning("⚠️ Amendment appeared successful but verification failed")
                    return False, "Amendment verification failed", None
            else:
                error_msg = amend_result.get("retMsg", "Unknown amend error") if amend_result else "No response from amend"
                logger.warning(f"⚠️ Amend operation failed: {error_msg}")
                return False, f"Amend failed: {error_msg}", None

        except Exception as e:
            logger.error(f"❌ Exception in amend approach: {e}")
            return False, f"Amend approach exception: {str(e)}", None

    async def _try_atomic_cancel_replace(
        self,
        monitor_data: Dict,
        entry_price: Decimal,
        current_price: Decimal
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Atomic cancel and replace with immediate rollback on failure"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            sl_order = monitor_data.get("sl_order", {})

            if not sl_order or not sl_order.get("order_id"):
                return False, "No existing SL order to replace", None

            # Store original order details for rollback
            original_order_id = sl_order["order_id"]
            original_sl_price = sl_order.get("price")
            original_quantity = monitor_data.get("remaining_size", monitor_data["position_size"])

            # Calculate breakeven price
            breakeven_price = self._calculate_breakeven_price(entry_price, side, 0)

            # Pre-verify new order parameters
            position_idx = await get_correct_position_idx(symbol, side)
            sl_side = "Sell" if side == "Buy" else "Buy"

            logger.info(f"🔄 Attempting atomic cancel/replace for {symbol} SL: {original_sl_price} → {breakeven_price}")

            # Step 1: Cancel existing order
            cancel_success = await cancel_order_with_retry(symbol, original_order_id, max_retries=2)

            if not cancel_success:
                return False, "Failed to cancel existing SL order", None

            logger.info(f"✅ Successfully cancelled original SL order {original_order_id[:8]}...")

            # Step 2: Immediately place new order
            try:
                new_sl_result = await place_order_with_retry(
                    symbol=symbol,
                    side=sl_side,
                    order_type="Market",
                    qty=str(original_quantity),
                    trigger_price=str(breakeven_price),
                    reduce_only=True,
                    order_link_id=sl_order.get("order_link_id", "") + "_BE_ATOMIC",
                    position_idx=position_idx,
                    stop_order_type="StopLoss"
                )

                if new_sl_result and new_sl_result.get("orderId"):
                    new_order_id = new_sl_result["orderId"]

                    # Step 3: Verify new order
                    await asyncio.sleep(1)
                    verification_success = await self._verify_sl_order(symbol, new_order_id, breakeven_price)

                    if verification_success:
                        new_sl_data = {
                            "order_id": new_order_id,
                            "price": breakeven_price,
                            "order_link_id": sl_order.get("order_link_id", "") + "_BE_ATOMIC",
                            "method": "cancel_replace"
                        }
                        logger.info(f"✅ Successfully replaced SL with atomic method")
                        return True, "SL replaced atomically", new_sl_data
                    else:
                        logger.error("❌ New SL order verification failed - attempting emergency rollback")
                        await self._emergency_rollback(monitor_data, original_sl_price, original_quantity)
                        return False, "New SL verification failed, emergency rollback attempted", None
                else:
                    logger.error("❌ Failed to place new SL order - attempting emergency rollback")
                    await self._emergency_rollback(monitor_data, original_sl_price, original_quantity)
                    return False, "Failed to place new SL, emergency rollback attempted", None

            except Exception as e:
                logger.error(f"❌ Exception placing new SL - attempting emergency rollback: {e}")
                await self._emergency_rollback(monitor_data, original_sl_price, original_quantity)
                return False, f"Exception in new SL placement: {str(e)}", None

        except Exception as e:
            logger.error(f"❌ Exception in atomic cancel/replace: {e}")
            return False, f"Atomic operation exception: {str(e)}", None

    async def _try_progressive_retry(
        self,
        monitor_data: Dict,
        entry_price: Decimal,
        current_price: Decimal
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Try multiple breakeven prices with progressive adjustments"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            logger.info(f"🔄 Starting progressive retry for {symbol} {side}")

            # Try each breakeven price adjustment
            for i, fee_adjustment in enumerate(self.breakeven_price_adjustments):
                logger.info(f"🎯 Progressive retry attempt {i+1}/{len(self.breakeven_price_adjustments)} with {fee_adjustment:.4f}% adjustment")

                # Calculate breakeven price with this adjustment
                breakeven_price = self._calculate_breakeven_price(entry_price, side, fee_adjustment)

                # Try to place SL at this price
                success, message, sl_data = await self._place_emergency_sl(
                    monitor_data, breakeven_price, f"progressive_{i+1}"
                )

                if success:
                    logger.info(f"✅ Progressive retry succeeded on attempt {i+1}")
                    return True, f"Progressive retry succeeded with {fee_adjustment:.4f}% adjustment", sl_data

                logger.warning(f"⚠️ Progressive retry attempt {i+1} failed: {message}")
                await asyncio.sleep(0.5)  # Brief delay between attempts

            return False, "All progressive retry attempts failed", None

        except Exception as e:
            logger.error(f"❌ Exception in progressive retry: {e}")
            return False, f"Progressive retry exception: {str(e)}", None

    async def _activate_emergency_protection(
        self,
        monitor_data: Dict,
        entry_price: Decimal,
        current_price: Decimal
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Activate emergency manual protection mode"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            position_key = f"{symbol}_{side}"

            logger.warning(f"🚨 Activating emergency protection for {position_key}")

            # Calculate emergency SL price (more conservative)
            emergency_offset = self.emergency_sl_offset_percent
            if side == "Buy":
                emergency_sl_price = current_price * (Decimal("1") - emergency_offset)
            else:  # Sell
                emergency_sl_price = current_price * (Decimal("1") + emergency_offset)

            # Place emergency SL
            success, message, sl_data = await self._place_emergency_sl(
                monitor_data, emergency_sl_price, "emergency"
            )

            if success:
                # Mark position as in emergency mode
                if position_key in self.protection_states:
                    self.protection_states[position_key].emergency_mode = True
                    self.protection_states[position_key].status = ProtectionStatus.EMERGENCY_MODE

                logger.warning(f"🚨 Emergency protection activated for {position_key}")
                return True, "Emergency protection activated", sl_data
            else:
                return False, f"Emergency protection failed: {message}", None

        except Exception as e:
            logger.error(f"❌ Exception in emergency protection: {e}")
            return False, f"Emergency protection exception: {str(e)}", None

    async def _place_emergency_sl(
        self,
        monitor_data: Dict,
        sl_price: Decimal,
        suffix: str
    ) -> Tuple[bool, str, Optional[Dict]]:
        """Place an emergency SL order"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            quantity = monitor_data.get("remaining_size", monitor_data["position_size"])

            sl_side = "Sell" if side == "Buy" else "Buy"
            position_idx = await get_correct_position_idx(symbol, side)

            # Generate unique order link ID
            order_link_id = f"BOT_EMERGENCY_SL_{symbol}_{suffix}_{int(time.time())}"

            sl_result = await place_order_with_retry(
                symbol=symbol,
                side=sl_side,
                order_type="Market",
                qty=str(quantity),
                trigger_price=str(sl_price),
                reduce_only=True,
                order_link_id=order_link_id,
                position_idx=position_idx,
                stop_order_type="StopLoss"
            )

            if sl_result and sl_result.get("orderId"):
                new_order_id = sl_result["orderId"]

                # Verify the order
                await asyncio.sleep(1)
                verification_success = await self._verify_sl_order(symbol, new_order_id, sl_price)

                if verification_success:
                    sl_data = {
                        "order_id": new_order_id,
                        "price": sl_price,
                        "order_link_id": order_link_id,
                        "method": f"emergency_{suffix}"
                    }
                    return True, "Emergency SL placed successfully", sl_data
                else:
                    return False, "Emergency SL verification failed", None
            else:
                error_msg = sl_result.get("retMsg", "Unknown error") if sl_result else "No response"
                return False, f"Emergency SL placement failed: {error_msg}", None

        except Exception as e:
            logger.error(f"❌ Exception placing emergency SL: {e}")
            return False, f"Emergency SL exception: {str(e)}", None

    async def _emergency_rollback(
        self,
        monitor_data: Dict,
        original_sl_price: Decimal,
        original_quantity: Decimal
    ) -> bool:
        """Emergency rollback to restore original SL"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            logger.warning(f"🔄 Attempting emergency rollback for {symbol} {side}")

            success, message, sl_data = await self._place_emergency_sl(
                monitor_data, original_sl_price, "rollback"
            )

            if success:
                logger.info(f"✅ Emergency rollback successful for {symbol} {side}")
                return True
            else:
                logger.error(f"❌ Emergency rollback failed for {symbol} {side}: {message}")
                return False

        except Exception as e:
            logger.error(f"❌ Exception in emergency rollback: {e}")
            return False

    async def _verify_sl_order(
        self,
        symbol: str,
        order_id: str,
        expected_price: Decimal,
        tolerance: Decimal = Decimal("0.000001")
    ) -> bool:
        """Verify that SL order exists and has correct parameters"""
        try:
            # Get open orders to verify
            orders = await get_open_orders(symbol)

            if not orders:
                logger.warning(f"⚠️ No open orders found for {symbol}")
                return False

            for order in orders:
                if order.get("orderId") == order_id:
                    order_trigger_price = Decimal(str(order.get("triggerPrice", "0")))
                    price_diff = abs(order_trigger_price - expected_price)

                    if price_diff <= tolerance:
                        logger.debug(f"✅ SL order {order_id[:8]}... verified at price {order_trigger_price}")
                        return True
                    else:
                        logger.warning(f"⚠️ SL order {order_id[:8]}... price mismatch: expected {expected_price}, got {order_trigger_price}")
                        return False

            logger.warning(f"⚠️ SL order {order_id[:8]}... not found in open orders")
            return False

        except Exception as e:
            logger.error(f"❌ Exception verifying SL order: {e}")
            return False

    def _calculate_breakeven_price(
        self,
        entry_price: Decimal,
        side: str,
        additional_adjustment: Decimal = Decimal("0")
    ) -> Decimal:
        """Calculate breakeven price with configurable adjustments"""
        base_fee = Decimal("0.0006")  # 0.06% base fee
        safety_margin = Decimal(str(BREAKEVEN_SAFETY_MARGIN))
        total_adjustment = base_fee + safety_margin + additional_adjustment

        if side == "Buy":
            return entry_price * (Decimal("1") + total_adjustment)
        else:  # Sell
            return entry_price * (Decimal("1") - total_adjustment)

    def _is_breakeven_beneficial(
        self,
        current_sl_price: Decimal,
        breakeven_price: Decimal,
        side: str
    ) -> bool:
        """Check if moving to breakeven price is beneficial"""
        if side == "Buy":
            return breakeven_price > current_sl_price
        else:  # Sell
            return breakeven_price < current_sl_price

    async def _record_success(
        self,
        position_key: str,
        method: BreakevenMethod,
        sl_data: Dict
    ):
        """Record successful breakeven attempt"""
        attempt = BreakevenAttempt(
            method=method,
            timestamp=time.time(),
            success=True,
            new_order_id=sl_data.get("order_id")
        )

        if position_key not in self.breakeven_attempts:
            self.breakeven_attempts[position_key] = []

        self.breakeven_attempts[position_key].append(attempt)

        # Update protection state
        if position_key in self.protection_states:
            state = self.protection_states[position_key]
            state.status = ProtectionStatus.PROTECTED
            state.sl_order_id = sl_data.get("order_id")
            state.sl_price = sl_data.get("price")
            state.last_verified = time.time()

    async def _send_breakeven_success_alert(
        self,
        monitor_data: Dict,
        sl_data: Dict,
        method: str
    ):
        """Send success alert for breakeven operation"""
        try:
            chat_id = monitor_data["chat_id"]
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            message = f"""🛡️ <b>BREAKEVEN SUCCESS - {method.upper()}</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

✅ <b>SL MOVED TO BREAKEVEN!</b>
🔧 Method: {method}
💰 New SL: ${sl_data.get('price', 'N/A'):.6f}
🆔 Order ID: {sl_data.get('order_id', 'N/A')[:8]}...

🔒 <b>Position Protection:</b>
• Risk-free position achieved
• Advanced failsafe system active
• Continuous monitoring enabled

✨ Your position is now fully protected!"""

            await send_simple_alert(chat_id, message, "breakeven_success")

        except Exception as e:
            logger.error(f"Error sending breakeven success alert: {e}")

    async def _send_emergency_protection_alert(
        self,
        monitor_data: Dict,
        sl_data: Dict
    ):
        """Send alert for emergency protection activation"""
        try:
            chat_id = monitor_data["chat_id"]
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            message = f"""🚨 <b>EMERGENCY PROTECTION ACTIVATED</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

⚠️ <b>FALLBACK PROTECTION ENGAGED</b>
🛡️ Emergency SL: ${sl_data.get('price', 'N/A'):.6f}
🆔 Order ID: {sl_data.get('order_id', 'N/A')[:8]}...

🔧 <b>What Happened:</b>
• Standard breakeven methods failed
• Emergency protection system activated
• Position remains protected

🔍 <b>Next Steps:</b>
• Manual review recommended
• Position monitoring continues
• Contact support if needed"""

            await send_simple_alert(chat_id, message, "emergency_protection")

        except Exception as e:
            logger.error(f"Error sending emergency protection alert: {e}")

    async def _handle_complete_failure(
        self,
        monitor_data: Dict,
        chat_id: int
    ):
        """Handle complete failure of all breakeven methods"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            position_key = f"{symbol}_{side}"

            # Update protection state
            if position_key in self.protection_states:
                self.protection_states[position_key].status = ProtectionStatus.UNPROTECTED

            message = f"""🚨 <b>CRITICAL: POSITION UNPROTECTED</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

❌ <b>ALL PROTECTION METHODS FAILED</b>
⚠️ Position has NO stop loss protection
🚨 IMMEDIATE MANUAL ACTION REQUIRED

🔧 <b>Failed Methods:</b>
• Amend existing SL ❌
• Cancel/Replace SL ❌
• Progressive retry ❌
• Emergency protection ❌

🚀 <b>URGENT ACTIONS:</b>
1. Manually place stop loss immediately
2. Monitor position closely
3. Consider closing position
4. Contact support

⚠️ This is a critical situation requiring immediate attention!"""

            await send_simple_alert(chat_id, message, "critical_failure")

        except Exception as e:
            logger.error(f"Error handling complete failure: {e}")

# Global instance
breakeven_failsafe = BreakevenFailsafeManager()