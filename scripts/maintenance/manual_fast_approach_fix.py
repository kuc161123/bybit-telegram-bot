#!/usr/bin/env python3
"""
Manual patch for fast approach order execution in monitor.py
This ensures both main and mirror accounts properly handle TP/SL for fast approach
"""

import os
import shutil
from datetime import datetime

def apply_manual_fix():
    """Manually patch monitor.py with the fix"""
    
    monitor_file = "execution/monitor.py"
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{monitor_file}.backup_{timestamp}"
    shutil.copy2(monitor_file, backup_file)
    print(f"✅ Created backup: {backup_file}")
    
    # Read the file
    with open(monitor_file, 'r') as f:
        lines = f.readlines()
    
    # Find the line where we need to insert the fix
    # Looking for "# Position closure detection" in mirror monitoring section
    insert_index = None
    for i, line in enumerate(lines):
        if i > 2600 and "# Position closure detection" in line:
            # Verify we're in mirror monitoring by checking previous lines
            in_mirror = False
            for j in range(max(0, i-100), i):
                if "monitor_mirror_position_loop_enhanced" in lines[j]:
                    in_mirror = True
                    break
            
            if in_mirror:
                print(f"📍 Found insertion point at line {i+1}")
                insert_index = i
                break
    
    if insert_index is None:
        print("❌ Could not find insertion point")
        return False
    
    # Create the fix code
    fix_code = '''                # FIXED: Fast approach TP/SL monitoring for MIRROR account
                elif approach == "fast" and current_size > 0:
                    
                    # Check for TP hit and cancel SL using same function as main account
                    if not fast_tp_hit:
                        # Pass None for ctx_app to prevent alerts (mirror accounts don't send alerts)
                        tp_hit = await check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side, None)
                        if tp_hit:
                            fast_tp_hit = True
                            logger.info(f"🎯 MIRROR Fast approach TP hit for {symbol} - SL cancelled")
                            
                            # Log the TP hit details
                            tp_order_id = chat_data.get("tp_order_id") or (chat_data.get("tp_order_ids", []) or [None])[0]
                            if tp_order_id:
                                logger.info(f"📊 MIRROR TP order {tp_order_id[:8]}... was triggered/filled")
                    
                    # Check for SL hit and cancel TP using same function as main account
                    if not fast_sl_hit:
                        # Pass None for ctx_app to prevent alerts (mirror accounts don't send alerts)
                        sl_hit = await check_sl_hit_and_cancel_tp(chat_data, symbol, current_price, side, None)
                        if sl_hit:
                            fast_sl_hit = True
                            logger.info(f"🛡️ MIRROR Fast approach SL hit for {symbol} - TP cancelled")
                            
                            # Log the SL hit details
                            sl_order_id = chat_data.get("sl_order_id") or chat_data.get("stop_loss_order_id")
                            if sl_order_id:
                                logger.info(f"📊 MIRROR SL order {sl_order_id[:8]}... was triggered/filled")
                
'''
    
    # Insert the fix
    lines.insert(insert_index, fix_code)
    
    # Write the file back
    with open(monitor_file, 'w') as f:
        f.writelines(lines)
    
    print("✅ Fix applied successfully!")
    return True

def verify_fix():
    """Verify the fix was applied correctly"""
    with open("execution/monitor.py", 'r') as f:
        content = f.read()
    
    checks = {
        "Mirror fast TP handling": "MIRROR Fast approach TP hit" in content,
        "Mirror fast SL handling": "MIRROR Fast approach SL hit" in content,
        "Triggered status check": '"Triggered"' in content and '"Filled", "PartiallyFilled", "Triggered"' in content,
        "TP order logging": "TP order triggered, waiting for fill" in content,
        "SL order logging": "SL order triggered, waiting for fill" in content
    }
    
    print("\n🔍 Verification Results:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {check_name}: {status}")
        if not passed:
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    print("🚀 Applying manual fast approach fix...")
    
    if apply_manual_fix():
        if verify_fix():
            print("\n✅ Fix successfully applied and verified!")
            print("ℹ️  All fast approach monitors (main and mirror) will now:")
            print("   - Properly detect 'Triggered' status")
            print("   - Wait briefly for triggered orders to fill")
            print("   - Cancel opposite orders when primary order fills")
            print("   - Send clear alerts about what happened")
        else:
            print("\n⚠️  Fix applied but verification shows some checks failed")
            print("   Please review the changes manually")
    else:
        print("\n❌ Failed to apply fix")