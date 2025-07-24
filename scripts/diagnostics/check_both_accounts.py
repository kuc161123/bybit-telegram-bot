#!/usr/bin/env python3
"""
Check both main and mirror accounts for positions and orders
"""

import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_position_info, get_active_tp_sl_orders
from config.settings import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AccountChecker:
    def __init__(self):
        self.symbols_to_check = ["JTOUSDT"]  # Add more symbols if needed
        
    async def check_account_positions_and_orders(self, account_name="Main"):
        """Check all positions and orders for an account"""
        print(f"\n{'='*80}")
        print(f"📊 {account_name.upper()} ACCOUNT STATUS")
        print(f"{'='*80}")
        
        all_positions_found = False
        
        for symbol in self.symbols_to_check:
            try:
                # Get position info
                logger.info(f"Checking {symbol} position...")
                positions = await get_position_info(symbol)
                position = positions[0] if positions and len(positions) > 0 else None
                
                # Get orders
                logger.info(f"Checking {symbol} orders...")
                orders = await get_active_tp_sl_orders(symbol)
                
                if position and float(position.get('size', 0)) > 0:
                    all_positions_found = True
                    await self.print_symbol_analysis(symbol, position, orders)
                elif orders:
                    print(f"\n❓ {symbol}: No position but {len(orders)} orders found")
                    await self.print_symbol_analysis(symbol, None, orders)
                else:
                    print(f"\n✅ {symbol}: No position, no orders (clean)")
                    
            except Exception as e:
                print(f"\n❌ Error checking {symbol}: {e}")
        
        if not all_positions_found:
            print(f"\n✅ {account_name} account: No active positions found")
        
        return all_positions_found
    
    async def print_symbol_analysis(self, symbol, position, orders):
        """Print detailed analysis for a symbol"""
        print(f"\n📈 {symbol} ANALYSIS:")
        print("-" * 50)
        
        # Position info
        if position:
            size = float(position.get('size', 0))
            avg_price = float(position.get('avgPrice', 0))
            pnl = float(position.get('unrealisedPnl', 0))
            side = position.get('side', 'Unknown')
            print(f"💰 Position: {size} {symbol} ({side}) @ ${avg_price:.6f}")
            print(f"📊 P&L: ${pnl:.2f}")
        else:
            print("💰 Position: None")
        
        # Orders analysis
        if orders:
            print(f"📋 Orders ({len(orders)}):")
            
            # Classify orders
            tp_orders = []
            sl_orders = []
            other_orders = []
            
            total_tp_qty = 0
            total_sl_qty = 0
            
            for order in orders:
                order_link_id = order.get('orderLinkId', 'N/A')
                side = order.get('side', '')
                qty = float(order.get('qty', 0))
                price = order.get('triggerPrice', order.get('price', 0))
                order_type = order.get('orderType', 'Unknown')
                stop_order_type = order.get('stopOrderType', '')
                
                # Determine if TP or SL based on patterns and stop order type
                if ('TP' in order_link_id or 'TakeProfit' in stop_order_type or 
                    'take_profit' in order_link_id.lower()):
                    tp_orders.append((order_link_id, qty, price, order_type))
                    total_tp_qty += qty
                elif ('SL' in order_link_id or 'StopLoss' in stop_order_type or 
                      'stop_loss' in order_link_id.lower()):
                    sl_orders.append((order_link_id, qty, price, order_type))
                    total_sl_qty += qty
                else:
                    other_orders.append((order_link_id, qty, price, order_type))
            
            # Print TP orders
            if tp_orders:
                print(f"   🎯 Take Profit Orders ({len(tp_orders)}):")
                for link_id, qty, price, order_type in tp_orders:
                    print(f"      • {qty} @ ${price} | {order_type} | {link_id}")
                print(f"   📊 Total TP Quantity: {total_tp_qty}")
            
            # Print SL orders  
            if sl_orders:
                print(f"   🛡️ Stop Loss Orders ({len(sl_orders)}):")
                for link_id, qty, price, order_type in sl_orders:
                    print(f"      • {qty} @ ${price} | {order_type} | {link_id}")
                print(f"   📊 Total SL Quantity: {total_sl_qty}")
            
            # Print other orders
            if other_orders:
                print(f"   ❓ Other Orders ({len(other_orders)}):")
                for link_id, qty, price, order_type in other_orders:
                    print(f"      • {qty} @ ${price} | {order_type} | {link_id}")
            
            # Quantity validation
            if position:
                position_size = float(position.get('size', 0))
                print(f"\n📊 QUANTITY VALIDATION:")
                print(f"   Position Size: {position_size}")
                print(f"   TP Orders Total: {total_tp_qty}")
                print(f"   SL Orders Total: {total_sl_qty}")
                
                # Check for over-allocation
                if total_tp_qty > position_size * 1.1:  # 10% tolerance
                    over_percent = (total_tp_qty / position_size - 1) * 100
                    print(f"   ⚠️ TP OVER-ALLOCATED: {over_percent:.1f}% too much")
                else:
                    print(f"   ✅ TP quantities look correct")
                
                if total_sl_qty > position_size * 1.1:  # 10% tolerance
                    over_percent = (total_sl_qty / position_size - 1) * 100
                    print(f"   ⚠️ SL OVER-ALLOCATED: {over_percent:.1f}% too much")
                else:
                    print(f"   ✅ SL quantities look correct")
        else:
            print("📋 Orders: None")
    
    async def run_check(self):
        """Run comprehensive check on both accounts"""
        print("\n" + "="*100)
        print("🔍 COMPREHENSIVE ACCOUNT STATUS CHECK")
        print("="*100)
        
        # Check main account
        main_has_positions = await self.check_account_positions_and_orders("Main")
        
        # Check mirror account (if available)
        try:
            # Switch to mirror account temporarily for checking
            # This would require implementing mirror account switching
            # For now, we'll just note that mirror checking would go here
            print(f"\n{'='*80}")
            print("📋 MIRROR ACCOUNT STATUS")
            print("="*80)
            print("🔧 Mirror account checking requires additional implementation")
            print("   (Would check BYBIT_API_KEY_2 / BYBIT_API_SECRET_2 if configured)")
            
        except Exception as e:
            print(f"\n❌ Could not check mirror account: {e}")
        
        # Summary
        print(f"\n{'='*80}")
        print("📋 SUMMARY")
        print("="*80)
        if main_has_positions:
            print("✅ Main account has active positions - monitor is likely running")
        else:
            print("🟡 Main account has no active positions")
            
        print("\n🎉 Status check completed!")

async def main():
    """Main execution function"""
    checker = AccountChecker()
    await checker.run_check()

if __name__ == "__main__":
    asyncio.run(main())