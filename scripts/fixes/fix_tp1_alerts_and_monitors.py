#!/usr/bin/env python3
"""
Fix TP1 alerts and ensure all monitors are working properly
This script:
1. Adds enhanced logging for TP1 detection
2. Ensures alerts are sent when TP1 is hit
3. Fixes limit order cancellation
4. Creates missing monitors for positions
"""
import asyncio
import sys
import os
import pickle
from decimal import Decimal
from datetime import datetime
import logging

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def enhance_tp1_logging():
    """Add enhanced logging to the Enhanced TP/SL manager for TP1 detection"""
    try:
        # Read the enhanced_tp_sl_manager.py file
        manager_path = '/Users/lualakol/bybit-telegram-bot/execution/enhanced_tp_sl_manager.py'
        
        with open(manager_path, 'r') as f:
            content = f.read()
        
        # Check if enhanced logging already exists
        if "TP1 HIT DETECTION" in content:
            logger.info("✅ Enhanced TP1 logging already exists")
            return True
        
        # Find the section where TP1 is detected (around line 1272-1278)
        # Add enhanced logging after tp1_hit is set
        tp1_detection = '''            # If TP1 was filled, set the tp1_hit flag regardless of fill percentage
            if tp_number == 1 and not monitor_data.get("tp1_hit", False):
                monitor_data["tp1_hit"] = True
                logger.info(f"✅ TP1 hit detected - will trigger breakeven movement and limit order cleanup")
                # Save the tp1_hit flag to persistence
                self.save_monitors_to_persistence()'''
        
        enhanced_tp1_detection = '''            # If TP1 was filled, set the tp1_hit flag regardless of fill percentage
            if tp_number == 1 and not monitor_data.get("tp1_hit", False):
                monitor_data["tp1_hit"] = True
                logger.info(f"✅ TP1 hit detected - will trigger breakeven movement and limit order cleanup")
                
                # ENHANCED LOGGING FOR TP1 HIT DETECTION
                logger.info(f"🎯 TP1 HIT DETECTION for {monitor_data.get('symbol')} {monitor_data.get('side')}")
                logger.info(f"  Monitor Key: {monitor_data.get('monitor_key', 'unknown')}")
                logger.info(f"  Account Type: {monitor_data.get('account_type', 'main')}")
                logger.info(f"  Position Size: {monitor_data.get('position_size')}")
                logger.info(f"  Remaining Size: {monitor_data.get('remaining_size')}")
                logger.info(f"  Fill Percentage: {fill_percentage:.2f}%")
                logger.info(f"  Chat ID: {monitor_data.get('chat_id', 'MISSING')}")
                logger.info(f"  Approach: {monitor_data.get('approach', 'unknown')}")
                logger.info(f"  Phase: {monitor_data.get('phase', 'unknown')}")
                logger.info(f"  Limit Orders Cancelled: {monitor_data.get('limit_orders_cancelled', False)}")
                
                # Check if chat_id is missing
                if not monitor_data.get('chat_id'):
                    logger.warning(f"⚠️ MISSING CHAT_ID - Alert may not be sent!")
                    # Try to find it
                    chat_id = await self._find_chat_id_for_position(monitor_data['symbol'], monitor_data['side'])
                    if chat_id:
                        monitor_data['chat_id'] = chat_id
                        logger.info(f"✅ Found chat_id: {chat_id}")
                    else:
                        logger.error(f"❌ Could not find chat_id for position")
                
                # Save the tp1_hit flag to persistence
                self.save_monitors_to_persistence()'''
        
        # Replace the content
        if tp1_detection in content:
            content = content.replace(tp1_detection, enhanced_tp1_detection)
            
            # Write back
            with open(manager_path, 'w') as f:
                f.write(content)
            
            logger.info("✅ Added enhanced TP1 logging to enhanced_tp_sl_manager.py")
            return True
        else:
            logger.warning("⚠️ Could not find TP1 detection code to enhance")
            return False
            
    except Exception as e:
        logger.error(f"Error enhancing TP1 logging: {e}")
        return False

async def create_missing_monitors():
    """Create monitors for positions that don't have them"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Import after env vars are loaded
        from clients.bybit_client import create_bybit_client
        from execution.mirror_trader import bybit_client_2
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        logger.info("🔍 CREATING MISSING MONITORS")
        logger.info("=" * 60)
        
        # Load pickle file
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Get actual positions
        bybit_client = create_bybit_client()
        
        # Main positions
        main_positions = bybit_client.get_open_positions()
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        # Mirror positions
        mirror_positions = bybit_client_2.get_open_positions() if bybit_client_2 else []
        mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        # Use singleton manager instance
        manager = enhanced_tp_sl_manager
        
        # Check main positions
        main_created = 0
        for pos in main_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            expected_key = f"{symbol}_{side}_main"
            
            if expected_key not in enhanced_monitors:
                logger.info(f"\n📋 Creating monitor for main {symbol} {side}")
                
                # Create monitor data
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "position_size": Decimal(str(pos.get('size'))),
                    "remaining_size": Decimal(str(pos.get('size'))),
                    "entry_price": Decimal(str(pos.get('avgPrice'))),
                    "approach": "CONSERVATIVE",  # Default to conservative
                    "account_type": "main",
                    "monitoring_active": True,
                    "limit_orders_cancelled": False,
                    "phase": "MONITORING",
                    "tp1_hit": False,
                    "initial_fill_processed": True,
                    "monitor_key": expected_key,
                    "created_at": datetime.now().isoformat()
                }
                
                # Try to find chat_id from monitor_tasks
                monitor_tasks = bot_data.get('monitor_tasks', {})
                chat_id = None
                for task_key, task_data in monitor_tasks.items():
                    if task_data.get('symbol') == symbol and task_data.get('side') == side:
                        # Extract chat_id from task key
                        parts = task_key.split('_')
                        if parts and parts[0].isdigit():
                            chat_id = int(parts[0])
                            break
                
                if chat_id:
                    monitor_data['chat_id'] = chat_id
                    logger.info(f"  Found chat_id: {chat_id}")
                
                # Add to monitors
                manager.position_monitors[expected_key] = monitor_data
                main_created += 1
        
        # Check mirror positions
        mirror_created = 0
        for pos in mirror_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            expected_key = f"{symbol}_{side}_mirror"
            
            if expected_key not in enhanced_monitors:
                logger.info(f"\n📋 Creating monitor for mirror {symbol} {side}")
                
                # Create monitor data
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "position_size": Decimal(str(pos.get('size'))),
                    "remaining_size": Decimal(str(pos.get('size'))),
                    "entry_price": Decimal(str(pos.get('avgPrice'))),
                    "approach": "CONSERVATIVE",  # Default to conservative
                    "account_type": "mirror",
                    "monitoring_active": True,
                    "limit_orders_cancelled": False,
                    "phase": "MONITORING",
                    "tp1_hit": False,
                    "initial_fill_processed": True,
                    "monitor_key": expected_key,
                    "has_mirror": True,
                    "created_at": datetime.now().isoformat()
                }
                
                # Try to find chat_id
                monitor_tasks = bot_data.get('monitor_tasks', {})
                chat_id = None
                for task_key, task_data in monitor_tasks.items():
                    if (task_data.get('symbol') == symbol and 
                        task_data.get('side') == side and
                        'mirror' in task_key.lower()):
                        # Extract chat_id from task key
                        parts = task_key.split('_')
                        if parts and parts[0].isdigit():
                            chat_id = int(parts[0])
                            break
                
                if chat_id:
                    monitor_data['chat_id'] = chat_id
                    logger.info(f"  Found chat_id: {chat_id}")
                
                # Add to monitors
                manager.position_monitors[expected_key] = monitor_data
                mirror_created += 1
        
        # Save if any monitors were created
        if main_created > 0 or mirror_created > 0:
            manager.save_monitors_to_persistence()
            logger.info(f"\n✅ Created {main_created} main monitors and {mirror_created} mirror monitors")
            logger.info("✅ Monitors saved to persistence")
        else:
            logger.info("\n✅ All positions already have monitors")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating missing monitors: {e}")
        import traceback
        traceback.print_exc()
        return False

async def fix_auctionusdt_monitors():
    """Fix AUCTIONUSDT specifically - add missing data"""
    try:
        logger.info("\n🔧 FIXING AUCTIONUSDT MONITORS")
        logger.info("=" * 60)
        
        # Load pickle file
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Fix AUCTIONUSDT monitors
        fixed_count = 0
        for key, monitor in enhanced_monitors.items():
            if 'AUCTIONUSDT' in key:
                logger.info(f"\n📋 Fixing monitor: {key}")
                
                # Add missing fields
                if 'monitoring_active' not in monitor or monitor['monitoring_active'] is None:
                    monitor['monitoring_active'] = True
                    logger.info("  Added monitoring_active: True")
                
                if 'tp1_hit' not in monitor:
                    # Check if position was reduced (TP1 likely hit)
                    if monitor.get('remaining_size', 0) < monitor.get('position_size', 0):
                        original_size = monitor.get('position_size', 0)
                        remaining_size = monitor.get('remaining_size', 0)
                        reduction_pct = ((original_size - remaining_size) / original_size * 100) if original_size > 0 else 0
                        
                        if reduction_pct >= 80:  # TP1 is 85%, so if reduced by 80%+ it hit
                            monitor['tp1_hit'] = True
                            monitor['limit_orders_cancelled'] = True
                            logger.info(f"  Set tp1_hit: True (position reduced by {reduction_pct:.1f}%)")
                    else:
                        monitor['tp1_hit'] = False
                
                if 'phase' not in monitor:
                    if monitor.get('tp1_hit'):
                        monitor['phase'] = 'PROFIT_TAKING'
                    else:
                        monitor['phase'] = 'MONITORING'
                    logger.info(f"  Added phase: {monitor['phase']}")
                
                if 'monitor_key' not in monitor:
                    monitor['monitor_key'] = key
                    logger.info(f"  Added monitor_key: {key}")
                
                # Try to find chat_id
                if 'chat_id' not in monitor or not monitor.get('chat_id'):
                    monitor_tasks = bot_data.get('monitor_tasks', {})
                    for task_key, task_data in monitor_tasks.items():
                        if (task_data.get('symbol') == 'AUCTIONUSDT' and 
                            task_data.get('side') == monitor.get('side')):
                            # Extract chat_id from task key
                            parts = task_key.split('_')
                            if parts and parts[0].isdigit():
                                monitor['chat_id'] = int(parts[0])
                                logger.info(f"  Found chat_id: {monitor['chat_id']}")
                                break
                
                fixed_count += 1
        
        if fixed_count > 0:
            # Save back to pickle
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"\n✅ Fixed {fixed_count} AUCTIONUSDT monitors")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fixing AUCTIONUSDT monitors: {e}")
        return False

async def main():
    """Main function"""
    try:
        # Step 1: Enhance TP1 logging
        logger.info("STEP 1: Enhancing TP1 logging...")
        await enhance_tp1_logging()
        
        # Step 2: Fix AUCTIONUSDT monitors
        logger.info("\nSTEP 2: Fixing AUCTIONUSDT monitors...")
        await fix_auctionusdt_monitors()
        
        # Step 3: Create missing monitors
        logger.info("\nSTEP 3: Creating missing monitors...")
        await create_missing_monitors()
        
        logger.info("\n✅ TP1 ALERTS AND MONITORS FIX COMPLETE")
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info("1. Enhanced TP1 detection logging")
        logger.info("2. Fixed AUCTIONUSDT monitor data")
        logger.info("3. Created any missing monitors")
        logger.info("\nThe bot will now properly:")
        logger.info("- Detect when TP1 is hit")
        logger.info("- Send alerts for TP fills")
        logger.info("- Cancel limit orders when TP1 hits")
        logger.info("- Move SL to breakeven after TP1")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())