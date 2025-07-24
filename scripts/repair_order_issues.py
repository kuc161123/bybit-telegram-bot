#!/usr/bin/env python3
"""
Repair Order Issues Utility

Fixes existing problematic orders that have:
1. Order link IDs longer than 45 characters
2. Invalid quantities that don't meet symbol requirements

This script can run without restarting the bot and will safely handle
both main and mirror accounts.
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import (
    get_open_orders_with_client, cancel_order_with_retry, place_order_with_retry,
    get_all_positions, adjust_quantity_to_step_size
)
from clients.bybit_client import bybit_client
from utils.order_identifier import generate_adjusted_order_link_id
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrderRepairManager:
    """Manages the repair of problematic orders"""
    
    def __init__(self):
        self.repaired_orders = []
        self.failed_repairs = []
        
    async def scan_and_repair_orders(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Scan all orders and repair problematic ones
        
        Args:
            dry_run: If True, only report issues without making changes
            
        Returns:
            Report of repairs made
        """
        logger.info(f"🔍 Starting order scan and repair (dry_run={dry_run})")
        
        report = {
            "main_account": await self._scan_account("main", dry_run),
            "mirror_account": await self._scan_account("mirror", dry_run) if self._is_mirror_available() else None
        }
        
        logger.info(f"✅ Order repair scan completed")
        return report
    
    async def _scan_account(self, account_type: str, dry_run: bool) -> Dict[str, Any]:
        """Scan orders for a specific account"""
        logger.info(f"📊 Scanning {account_type} account orders...")
        
        try:
            # Get client for account
            client = await self._get_client(account_type)
            if not client:
                return {"error": f"Could not get client for {account_type} account"}
            
            # Get all open orders
            response = await get_open_orders_with_client(client, category="linear", settleCoin="USDT")
            if response and hasattr(response, 'get') and response.get('retCode') == 0:
                all_orders = response.get('result', {}).get('list', [])
            else:
                all_orders = []
            logger.info(f"Found {len(all_orders)} orders in {account_type} account")
            
            problematic_orders = []
            
            # Check each order for issues
            for order in all_orders:
                issues = self._check_order_issues(order)
                if issues:
                    problematic_orders.append({
                        "order": order,
                        "issues": issues
                    })
            
            logger.info(f"Found {len(problematic_orders)} problematic orders in {account_type} account")
            
            # Repair orders if not dry run
            repairs_made = []
            if not dry_run and problematic_orders:
                repairs_made = await self._repair_orders(problematic_orders, client, account_type)
            
            return {
                "account_type": account_type,
                "total_orders": len(all_orders),
                "problematic_orders": len(problematic_orders),
                "issues_found": problematic_orders,
                "repairs_made": repairs_made
            }
            
        except Exception as e:
            logger.error(f"Error scanning {account_type} account: {e}")
            return {"error": str(e)}
    
    def _check_order_issues(self, order: Dict) -> List[str]:
        """Check an order for known issues"""
        issues = []
        
        order_link_id = order.get("orderLinkId", "")
        
        # Check order link ID length
        if len(order_link_id) > 45:
            issues.append(f"order_link_id_too_long_{len(order_link_id)}")
        
        # Check for multiple _ADJ suffixes
        if "_ADJ_ADJ" in order_link_id or order_link_id.count("_ADJ") > 1:
            issues.append("multiple_adj_suffixes")
        
        # Check for any _ADJ suffix (old format)
        if "_ADJ" in order_link_id and not "_A" in order_link_id:
            issues.append("old_adj_format")
        
        # Check for old CONSERVATIVE instead of CONS
        if "BOT_CONSERVATIVE_" in order_link_id:
            issues.append("unabbreviated_approach")
        
        # Check quantity format (basic check - detailed validation would require symbol info)
        qty = order.get("qty", "")
        if qty and "." in qty:
            decimal_places = len(qty.split(".")[1])
            if decimal_places > 8:  # Excessive decimal places
                issues.append(f"excessive_decimal_places_{decimal_places}")
        
        # Log problematic orders for debugging
        if issues:
            logger.info(f"🔍 Found problematic order: {order_link_id} (issues: {issues})")
        
        return issues
    
    async def _repair_orders(self, problematic_orders: List[Dict], client, account_type: str) -> List[Dict]:
        """Repair problematic orders"""
        repairs_made = []
        
        for item in problematic_orders:
            order = item["order"]
            issues = item["issues"]
            
            try:
                repair_result = await self._repair_single_order(order, issues, client, account_type)
                if repair_result:
                    repairs_made.append(repair_result)
                    
            except Exception as e:
                logger.error(f"Error repairing order {order.get('orderId', 'unknown')}: {e}")
                self.failed_repairs.append({
                    "order_id": order.get('orderId'),
                    "error": str(e)
                })
        
        return repairs_made
    
    async def _repair_single_order(self, order: Dict, issues: List[str], client, account_type: str) -> Dict:
        """Repair a single problematic order"""
        symbol = order.get("symbol")
        order_id = order.get("orderId")
        
        logger.info(f"🔧 Repairing order {order_id} for {symbol} (issues: {issues})")
        
        # First, cancel the problematic order
        cancel_success = await cancel_order_with_retry(
            symbol=symbol,
            order_id=order_id,
            client=client
        )
        
        if not cancel_success:
            raise Exception(f"Failed to cancel order {order_id}")
        
        # Prepare new order parameters
        new_params = {
            "symbol": symbol,
            "side": order.get("side"),
            "order_type": order.get("orderType"),
            "qty": order.get("qty"),
            "reduce_only": order.get("reduceOnly", False)
        }
        
        # Fix order link ID if needed
        original_link_id = order.get("orderLinkId", "")
        if any("order_link_id" in issue or "adj" in issue for issue in issues):
            # Generate new order link ID
            new_params["order_link_id"] = generate_adjusted_order_link_id(original_link_id, 1)
        else:
            new_params["order_link_id"] = original_link_id
        
        # Fix quantity if needed
        if any("decimal" in issue for issue in issues):
            new_params["qty"] = await adjust_quantity_to_step_size(symbol, new_params["qty"])
        
        # Add other parameters
        if order.get("price"):
            new_params["price"] = order["price"]
        if order.get("triggerPrice"):
            new_params["trigger_price"] = order["triggerPrice"]
        if order.get("stopOrderType"):
            new_params["stop_order_type"] = order["stopOrderType"]
        if order.get("timeInForce"):
            new_params["time_in_force"] = order["timeInForce"]
        
        # Place new order
        new_result = await place_order_with_retry(**new_params)
        
        if new_result and new_result.get("orderId"):
            repair_result = {
                "original_order_id": order_id,
                "new_order_id": new_result["orderId"],
                "symbol": symbol,
                "issues_fixed": issues,
                "original_link_id": original_link_id,
                "new_link_id": new_params["order_link_id"]
            }
            
            logger.info(f"✅ Successfully repaired order {order_id} → {new_result['orderId']}")
            self.repaired_orders.append(repair_result)
            return repair_result
        else:
            raise Exception(f"Failed to place replacement order for {order_id}")
    
    async def _get_client(self, account_type: str):
        """Get the appropriate client for account type"""
        if account_type == "main":
            return bybit_client
        elif account_type == "mirror":
            try:
                from execution.mirror_trader import bybit_client_2
                return bybit_client_2
            except ImportError:
                return None
        return None
    
    def _is_mirror_available(self) -> bool:
        """Check if mirror trading is available"""
        try:
            from execution.mirror_trader import is_mirror_trading_enabled
            return is_mirror_trading_enabled()
        except ImportError:
            return False

async def main():
    """Main function to run the repair process"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Repair problematic trading orders")
    parser.add_argument("--dry-run", action="store_true", help="Only scan and report, don't make changes")
    parser.add_argument("--account", choices=["main", "mirror", "both"], default="both", 
                       help="Which account to repair")
    
    args = parser.parse_args()
    
    repair_manager = OrderRepairManager()
    
    logger.info("🚀 Starting Order Repair Utility")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'REPAIR'}")
    logger.info(f"Account: {args.account}")
    use_testnet = os.getenv("USE_TESTNET", "false").lower() == "true"
    logger.info(f"Environment: {'TESTNET' if use_testnet else 'MAINNET'}")
    
    # Run the repair process
    report = await repair_manager.scan_and_repair_orders(dry_run=args.dry_run)
    
    # Print summary
    print("\n" + "="*60)
    print("ORDER REPAIR SUMMARY")
    print("="*60)
    
    for account_type, account_report in report.items():
        if account_report is None:
            continue
            
        print(f"\n{account_type.upper()} ACCOUNT:")
        if "error" in account_report:
            print(f"  ❌ Error: {account_report['error']}")
        else:
            print(f"  Total orders: {account_report['total_orders']}")
            print(f"  Problematic orders: {account_report['problematic_orders']}")
            print(f"  Repairs made: {len(account_report.get('repairs_made', []))}")
            
            if account_report['problematic_orders'] > 0:
                print("\n  Issues found:")
                for item in account_report['issues_found']:
                    order = item['order']
                    issues = item['issues']
                    print(f"    Order {order.get('orderId', 'unknown')} ({order.get('symbol', 'unknown')}): {', '.join(issues)}")
    
    print(f"\n{'DRY RUN COMPLETE' if args.dry_run else 'REPAIR COMPLETE'}")
    
    if args.dry_run and any(report.get(acc, {}).get('problematic_orders', 0) > 0 for acc in report):
        print("\nTo apply fixes, run: python scripts/repair_order_issues.py")

if __name__ == "__main__":
    asyncio.run(main())