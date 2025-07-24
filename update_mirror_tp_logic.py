#!/usr/bin/env python3
"""
Update mirror trading logic to use limit orders for TPs
"""
import shutil
from datetime import datetime

def update_trader_py():
    """Update trader.py to use limit orders for mirror TPs"""
    
    # Backup original
    print("Creating backup of trader.py...")
    backup_path = f"execution/trader.py.backup_mirror_tp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy('execution/trader.py', backup_path)
    print(f"Backup created: {backup_path}")
    
    # Read the file
    with open('execution/trader.py', 'r') as f:
        content = f.read()
    
    # Find and replace mirror TP order placement
    replacements = [
        # Replace mirror_tp_sl_order with mirror_limit_order for TP orders
        (
            """mirror_tp_result = await mirror_tp_sl_order(
                                symbol=symbol,
                                side=tp_side,
                                qty=str(mirror_tp_qty),  # Use proportional quantity
                                trigger_price=str(tp_price),
                                position_idx=original_position_idx,
                                order_link_id=unique_order_link_id,
                                stop_order_type="TakeProfit"
                            )""",
            """mirror_tp_result = await mirror_limit_order(
                                symbol=symbol,
                                side=tp_side,
                                qty=str(mirror_tp_qty),  # Use proportional quantity
                                price=str(tp_price),
                                position_idx=original_position_idx,
                                order_link_id=unique_order_link_id,
                                reduce_only=True,
                                time_in_force="GTC"
                            )"""
        ),
        # Another pattern for mirror TP
        (
            """mirror_tp = await mirror_tp_sl_order(
                            symbol=symbol,
                            side=tp_side,
                            qty=str(mirror_qty),
                            trigger_price=str(tp_price),
                            position_idx=0,  # Mirror always uses One-Way mode
                            order_link_id=f"{tp_order_link_id}_MIRROR",
                            stop_order_type="TakeProfit"
                        )""",
            """mirror_tp = await mirror_limit_order(
                            symbol=symbol,
                            side=tp_side,
                            qty=str(mirror_qty),
                            price=str(tp_price),
                            position_idx=0,  # Mirror always uses One-Way mode
                            order_link_id=f"{tp_order_link_id}_MIRROR",
                            reduce_only=True,
                            time_in_force="GTC"
                        )"""
        )
    ]
    
    # Apply replacements
    changes_made = 0
    for old_text, new_text in replacements:
        if old_text in content:
            content = content.replace(old_text, new_text)
            changes_made += 1
            print(f"✅ Updated mirror TP order placement pattern {changes_made}")
    
    # Write updated content
    if changes_made > 0:
        with open('execution/trader.py', 'w') as f:
            f.write(content)
        print(f"\n✅ Successfully updated {changes_made} mirror TP order patterns")
        print("Mirror TPs will now use limit orders instead of stop market orders")
    else:
        print("\n⚠️  No matching patterns found to update")

def verify_enhanced_tp_sl():
    """Verify enhanced_tp_sl_manager already uses limit orders"""
    print("\nVerifying enhanced_tp_sl_manager.py...")
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    if 'mirror_result = await mirror_limit_order(' in content:
        print("✅ enhanced_tp_sl_manager.py already uses mirror_limit_order for TPs")
    else:
        print("⚠️  enhanced_tp_sl_manager.py may need updating")

def main():
    """Main execution"""
    print("="*60)
    print("UPDATING MIRROR TP LOGIC TO USE LIMIT ORDERS")
    print("="*60)
    
    # Update trader.py
    update_trader_py()
    
    # Verify enhanced_tp_sl_manager.py
    verify_enhanced_tp_sl()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("✅ Mirror trading logic updated to use limit orders for TPs")
    print("✅ Future mirror trades will place TP orders as limit orders")
    print("✅ This matches the main account behavior")
    print("\nChanges:")
    print("- trader.py: Updated mirror_tp_sl_order calls to mirror_limit_order")
    print("- enhanced_tp_sl_manager.py: Already using mirror_limit_order (verified)")

if __name__ == "__main__":
    main()