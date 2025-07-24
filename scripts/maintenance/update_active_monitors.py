#!/usr/bin/env python3
"""
Update all active fast approach monitors to ensure they have proper flags
and will use the updated logic
"""

import asyncio
import pickle
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def update_monitors():
    """Update all active monitors with proper flags"""
    
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        # Load persistence data
        with open(persistence_file, 'rb') as f:
            data = pickle.load(f)
        
        logger.info(f"📂 Loaded persistence data with {len(data)} entries")
        
        updated_count = 0
        monitor_details = []
        
        # Process each chat's data
        for chat_id, chat_data in data.items():
            if not isinstance(chat_data, dict):
                continue
            
            # Check main account monitors
            if chat_data.get("active_monitor_task", {}).get("active", False):
                symbol = chat_data.get("symbol")
                approach = chat_data.get("trading_approach", "fast")
                
                if approach == "fast":
                    # Ensure proper flags exist
                    if "tp_hit_processed" not in chat_data:
                        chat_data["tp_hit_processed"] = False
                    if "sl_hit_processed" not in chat_data:
                        chat_data["sl_hit_processed"] = False
                    
                    # Ensure order IDs are properly stored
                    if "tp_order_id" not in chat_data and "tp_order_ids" in chat_data:
                        tp_ids = chat_data.get("tp_order_ids", [])
                        if tp_ids:
                            chat_data["tp_order_id"] = tp_ids[0]
                    
                    monitor_details.append({
                        "type": "MAIN",
                        "symbol": symbol,
                        "chat_id": chat_id,
                        "approach": approach
                    })
                    updated_count += 1
                    logger.info(f"✅ Updated MAIN fast monitor: {symbol} (chat {chat_id})")
            
            # Check mirror account monitors
            if chat_data.get("mirror_active_monitor_task", {}).get("active", False):
                symbol = chat_data.get("symbol")
                approach = chat_data.get("trading_approach", "fast")
                
                if approach == "fast":
                    # Ensure proper flags exist
                    if "tp_hit_processed" not in chat_data:
                        chat_data["tp_hit_processed"] = False
                    if "sl_hit_processed" not in chat_data:
                        chat_data["sl_hit_processed"] = False
                    
                    # Ensure mirror order IDs are properly stored
                    if "mirror_tp_order_id" not in chat_data and "mirror_tp_order_ids" in chat_data:
                        tp_ids = chat_data.get("mirror_tp_order_ids", [])
                        if tp_ids:
                            chat_data["mirror_tp_order_id"] = tp_ids[0]
                    
                    monitor_details.append({
                        "type": "MIRROR",
                        "symbol": symbol,
                        "chat_id": chat_id,
                        "approach": approach
                    })
                    updated_count += 1
                    logger.info(f"✅ Updated MIRROR fast monitor: {symbol} (chat {chat_id})")
        
        # Save updated data
        with open(persistence_file, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n📊 Update Summary:")
        logger.info(f"  Total monitors updated: {updated_count}")
        logger.info(f"  Main account monitors: {sum(1 for m in monitor_details if m['type'] == 'MAIN')}")
        logger.info(f"  Mirror account monitors: {sum(1 for m in monitor_details if m['type'] == 'MIRROR')}")
        
        if monitor_details:
            logger.info(f"\n📋 Active Fast Approach Monitors:")
            for monitor in monitor_details:
                logger.info(f"  - {monitor['type']}: {monitor['symbol']} (chat {monitor['chat_id']})")
        
        return updated_count
        
    except Exception as e:
        logger.error(f"❌ Error updating monitors: {e}")
        import traceback
        traceback.print_exc()
        return 0

async def verify_order_handling():
    """Verify that the monitor.py has proper order handling"""
    
    logger.info("\n🔍 Verifying order handling implementation...")
    
    with open("execution/monitor.py", 'r') as f:
        content = f.read()
    
    checks = {
        "Main account Triggered handling": 'if tp_status == "Triggered"' in content,
        "Main account Triggered in list": '"Triggered" in ["Filled", "PartiallyFilled", "Triggered"]' in content,
        "Mirror fast approach added": "MIRROR Fast approach TP hit" in content,
        "TP order wait logic": "TP order triggered, waiting for fill" in content,
        "SL order wait logic": "SL order triggered, waiting for fill" in content,
        "Order state logging": "Checking order" in content and "current status:" in content
    }
    
    all_good = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        logger.info(f"  {status} {check_name}")
        if not passed:
            all_good = False
    
    return all_good

async def main():
    """Main execution"""
    logger.info("🚀 Updating all active fast approach monitors...")
    
    # First verify the fix is in place
    if await verify_order_handling():
        logger.info("\n✅ Order handling implementation verified!")
    else:
        logger.warning("\n⚠️ Some order handling checks failed - please verify monitor.py")
        return
    
    # Update all active monitors
    count = await update_monitors()
    
    if count > 0:
        logger.info(f"\n✅ Successfully updated {count} fast approach monitors!")
        logger.info("\n📋 What happens now:")
        logger.info("  1. All monitors will properly detect 'Triggered' status")
        logger.info("  2. Brief wait (0.5s) when orders are triggered before checking fill")
        logger.info("  3. Opposite orders cancelled only when primary order fills")
        logger.info("  4. Clear alerts sent with details of cancelled orders")
        logger.info("  5. Both main and mirror accounts use identical logic")
    else:
        logger.info("\nℹ️ No active fast approach monitors found to update")

if __name__ == "__main__":
    asyncio.run(main())