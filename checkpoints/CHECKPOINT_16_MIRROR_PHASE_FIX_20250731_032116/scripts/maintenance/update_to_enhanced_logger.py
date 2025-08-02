#!/usr/bin/env python3
"""
Update all files to use the enhanced trade logger.
This will ensure comprehensive logging of all trade activities.
"""

import os
import re

def update_imports():
    """Update imports to use enhanced trade logger."""
    
    files_to_update = [
        "execution/monitor.py",
        "execution/trader.py",
        "utils/trade_verifier.py"
    ]
    
    updates_made = []
    
    for file_path in files_to_update:
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Replace trade_logger imports with enhanced_trade_logger
            patterns = [
                (r'from utils\.trade_logger import (.+)', r'from utils.enhanced_trade_logger import \1'),
                (r'import utils\.trade_logger', 'import utils.enhanced_trade_logger'),
                (r'from utils import trade_logger', 'from utils import enhanced_trade_logger as trade_logger'),
            ]
            
            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)
            
            # If content changed, write it back
            if content != original_content:
                with open(file_path, 'w') as f:
                    f.write(content)
                updates_made.append(file_path)
                print(f"✅ Updated: {file_path}")
            else:
                print(f"ℹ️  No changes needed: {file_path}")
                
        except Exception as e:
            print(f"❌ Error updating {file_path}: {e}")
    
    return updates_made

def create_logger_wrapper():
    """Create a wrapper to make enhanced logger compatible with existing code."""
    
    wrapper_content = '''#!/usr/bin/env python3
"""
Wrapper for enhanced trade logger to maintain compatibility with existing code.
"""

from utils.enhanced_trade_logger import (
    enhanced_trade_logger,
    log_trade_entry as enhanced_log_trade_entry,
    log_order_event,
    log_position_update,
    update_performance,
    get_active_trades,
    export_report
)

# Create wrapper class for compatibility
class TradeLoggerWrapper:
    """Wrapper to maintain compatibility with existing trade logger interface."""
    
    def __init__(self):
        self.logger = enhanced_trade_logger
    
    async def log_trade_entry(self, symbol, side, approach, entry_price, size, 
                            order_type="Market", chat_id=None, leverage=None, 
                            risk_percentage=None, **kwargs):
        """Log trade entry with enhanced details."""
        # Add any limit orders if passed
        limit_orders = kwargs.pop('limit_orders', [])
        take_profits = kwargs.pop('take_profits', [])
        stop_loss = kwargs.pop('stop_loss', None)
        
        return await enhanced_log_trade_entry(
            symbol=symbol,
            side=side,
            approach=approach,
            entry_price=entry_price,
            size=size,
            order_type=order_type,
            chat_id=chat_id,
            leverage=leverage,
            risk_percentage=risk_percentage,
            limit_orders=limit_orders,
            take_profits=take_profits,
            stop_loss=stop_loss,
            **kwargs
        )
    
    async def log_tp_orders(self, trade_key, tp_orders):
        """Log TP orders - now handled in trade entry."""
        # In enhanced logger, this is handled during trade entry
        # But we'll log as order events for compatibility
        if trade_key:
            for order in tp_orders:
                await log_order_event(
                    trade_key,
                    "placed",
                    "tp",
                    order.get('orderId', ''),
                    order
                )
    
    async def log_sl_order(self, trade_key, sl_order):
        """Log SL order - now handled in trade entry."""
        if trade_key:
            await log_order_event(
                trade_key,
                "placed",
                "sl",
                sl_order.get('orderId', ''),
                sl_order
            )
    
    async def log_order_fill(self, symbol, side, order_type, fill_price, fill_qty, order_id=None):
        """Log order fill."""
        # Find active trade for this symbol
        trades = await get_active_trades()
        for trade in trades:
            if trade['symbol'] == symbol and trade['side'] == side:
                await log_order_event(
                    trade['trade_id'],
                    "filled",
                    order_type.lower(),
                    order_id or '',
                    {
                        'fill_price': str(fill_price),
                        'fill_qty': str(fill_qty),
                        'order_type': order_type
                    }
                )
                break
    
    async def log_position_merge(self, symbol, side, approach, old_sizes, new_size, new_avg_price):
        """Log position merge."""
        trades = await get_active_trades()
        for trade in trades:
            if trade['symbol'] == symbol and trade['side'] == side:
                await log_position_update(
                    trade['trade_id'],
                    "merge",
                    {
                        'old_sizes': [str(s) for s in old_sizes],
                        'new_size': str(new_size),
                        'new_avg_price': str(new_avg_price)
                    }
                )
                break
    
    async def log_rebalance(self, symbol, side, approach, details):
        """Log rebalance event."""
        trades = await get_active_trades()
        for trade in trades:
            if trade['symbol'] == symbol and trade['side'] == side:
                await log_position_update(
                    trade['trade_id'],
                    "rebalance",
                    details
                )
                break

# Global instance
trade_logger = TradeLoggerWrapper()

# Export all functions for compatibility
__all__ = [
    'trade_logger',
    'log_order_event',
    'log_position_update',
    'update_performance',
    'get_active_trades',
    'export_report'
]
'''
    
    try:
        with open('utils/trade_logger_enhanced.py', 'w') as f:
            f.write(wrapper_content)
        print("✅ Created enhanced trade logger wrapper")
        return True
    except Exception as e:
        print(f"❌ Error creating wrapper: {e}")
        return False

def main():
    """Main function."""
    print("\n" + "="*60)
    print("UPDATING TO ENHANCED TRADE LOGGER")
    print("="*60)
    
    # Create wrapper first
    print("\n1. Creating compatibility wrapper...")
    if create_logger_wrapper():
        print("   ✅ Wrapper created successfully")
    
    # Update imports
    print("\n2. Updating imports in existing files...")
    updated_files = update_imports()
    
    print(f"\n✅ Updated {len(updated_files)} files")
    
    print("\n" + "="*60)
    print("ENHANCED LOGGING FEATURES")
    print("="*60)
    print("\n✅ Comprehensive trade tracking including:")
    print("   • All limit orders with prices and quantities")
    print("   • All TP/SL orders with trigger prices")
    print("   • Order modifications and cancellations")
    print("   • Position merges and splits")
    print("   • Rebalancing events")
    print("   • Performance metrics and P&L tracking")
    print("   • Risk management data")
    print("   • Complete order lifecycle")
    print("\n✅ Automatic archiving and compression")
    print("✅ Export capabilities for reporting")
    print("✅ JSON format for easy analysis")

if __name__ == "__main__":
    main()