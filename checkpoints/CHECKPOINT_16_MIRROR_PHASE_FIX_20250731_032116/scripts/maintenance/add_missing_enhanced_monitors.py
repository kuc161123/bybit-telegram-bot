#!/usr/bin/env python3
"""
Add missing Enhanced TP/SL monitors for existing positions
"""
import asyncio
import logging
import os
import sys
import time
from decimal import Decimal
import pickle
from pybit.unified_trading import HTTP

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("✅ Loaded environment variables from .env file")
except ImportError:
    logger.warning("❌ python-dotenv not installed, skipping .env file loading")

# Import required modules
from clients.bybit_helpers import get_all_positions as get_positions_helper
from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET

# Initialize mirror client if available
bybit_client_2 = None
if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
    try:
        bybit_client_2 = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        logger.info("✅ Mirror trading client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize mirror trading client: {e}")

async def get_all_positions():
    """Get all positions from main account"""
    try:
        positions = await get_positions_helper()
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        return active_positions
    except Exception as e:
        logger.error(f"Error getting main positions: {e}")
        return []

def get_mirror_positions():
    """Get all positions from mirror account"""
    if not bybit_client_2:
        return []
    
    try:
        response = bybit_client_2.get_positions(
            category="linear",
            settleCoin="USDT",
            limit=200
        )
        if response and response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
            return active_positions
        return []
    except Exception as e:
        logger.error(f"Error getting mirror positions: {e}")
        return []

async def create_enhanced_monitor(symbol: str, side: str, position_data: dict, is_mirror: bool = False):
    """Create Enhanced TP/SL monitor for a position"""
    try:
        # Import Enhanced TP/SL manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Prepare monitor data
        monitor_key = f"{symbol}_{side}"
        if is_mirror:
            monitor_key += "_MIRROR"
        
        # Create basic monitor structure
        monitor_data = {
            "symbol": symbol,
            "side": side,
            "entry_price": Decimal(str(position_data.get("avgPrice", 0))),
            "position_size": Decimal(str(position_data.get("size", 0))),
            "current_size": Decimal(str(position_data.get("size", 0))),
            "remaining_size": Decimal(str(position_data.get("size", 0))),
            "tp_orders": [],  # No TP orders for existing positions
            "sl_order": None,  # No SL order for existing positions
            "filled_tps": [],
            "approach": "conservative",  # Default approach
            "chat_id": 1,  # Default chat ID (should be updated)
            "created_at": time.time(),
            "last_check": time.time(),
            "sl_moved_to_be": False,
            "monitoring_task": None,
            "limit_orders": [],
            "limit_orders_filled": True,  # Assume position is fully built
            "phase": "PROFIT_TAKING",  # Already in profit-taking phase
            "tp1_hit": False,
            "phase_transition_time": None,
            "total_tp_filled": Decimal("0"),
            "cleanup_completed": False,
            "bot_instance": None,
            "is_manual_monitor": True,  # Mark as manually created
            "account_type": "mirror" if is_mirror else "main"
        }
        
        # Add to appropriate monitors
        if is_mirror:
            # Import mirror manager
            from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager
            if mirror_enhanced_tp_sl_manager:
                mirror_enhanced_tp_sl_manager.mirror_monitors[monitor_key] = monitor_data
                logger.info(f"✅ Created mirror monitor: {monitor_key}")
                
                # Start monitoring task
                monitor_task = asyncio.create_task(
                    monitor_enhanced_position(symbol, side, monitor_data, is_mirror=True)
                )
                monitor_data["monitoring_task"] = monitor_task
        else:
            enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
            logger.info(f"✅ Created main monitor: {monitor_key}")
            
            # Start monitoring task
            monitor_task = asyncio.create_task(
                monitor_enhanced_position(symbol, side, monitor_data, is_mirror=False)
            )
            monitor_data["monitoring_task"] = monitor_task
        
        # Create dashboard monitor entry
        await enhanced_tp_sl_manager.create_dashboard_monitor_entry(
            symbol=symbol,
            side=side,
            chat_id=1,  # Default chat ID
            approach="conservative",
            account_type="mirror" if is_mirror else "main"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating monitor for {symbol} {side} (mirror={is_mirror}): {e}")
        return False

async def monitor_enhanced_position(symbol: str, side: str, monitor_data: dict, is_mirror: bool = False):
    """Basic monitoring loop for manually created monitors"""
    monitor_key = f"{symbol}_{side}"
    if is_mirror:
        monitor_key += "_MIRROR"
    
    logger.info(f"🔄 Starting manual monitor loop for {monitor_key}")
    
    try:
        while True:
            # Check if position still exists
            if is_mirror:
                positions = get_mirror_positions()
            else:
                positions = await get_all_positions()
            
            position_exists = False
            for pos in positions:
                if pos.get("symbol") == symbol and pos.get("side") == side:
                    position_exists = True
                    break
            
            if not position_exists:
                logger.info(f"📍 Position {monitor_key} closed - stopping monitor")
                break
            
            # Wait before next check
            await asyncio.sleep(12)
            
    except asyncio.CancelledError:
        logger.info(f"⏹️ Monitor loop cancelled for {monitor_key}")
    except Exception as e:
        logger.error(f"❌ Error in monitor loop for {monitor_key}: {e}")

async def main():
    """Main function to add missing monitors"""
    logger.info("🔍 ADDING MISSING ENHANCED MONITORS")
    logger.info("=" * 60)
    
    # Get all positions
    main_positions = await get_all_positions()
    mirror_positions = get_mirror_positions() if bybit_client_2 else []
    
    logger.info(f"📈 Main Account Positions: {len(main_positions)}")
    logger.info(f"🪞 Mirror Account Positions: {len(mirror_positions)}")
    
    # Check existing monitors
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    existing_main_monitors = set(enhanced_tp_sl_manager.position_monitors.keys())
    
    try:
        from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager
        existing_mirror_monitors = set(mirror_enhanced_tp_sl_manager.mirror_monitors.keys()) if mirror_enhanced_tp_sl_manager else set()
    except:
        existing_mirror_monitors = set()
    
    logger.info(f"📊 Existing Main Monitors: {len(existing_main_monitors)}")
    logger.info(f"📊 Existing Mirror Monitors: {len(existing_mirror_monitors)}")
    
    # Find missing monitors
    monitors_created = 0
    
    # Add missing main monitors
    for pos in main_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        monitor_key = f"{symbol}_{side}"
        
        if monitor_key not in existing_main_monitors:
            logger.info(f"\n📍 Creating monitor for main {symbol} {side}")
            success = await create_enhanced_monitor(symbol, side, pos, is_mirror=False)
            if success:
                monitors_created += 1
            await asyncio.sleep(0.5)  # Small delay between creations
    
    # Add missing mirror monitors
    for pos in mirror_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        monitor_key = f"{symbol}_{side}_MIRROR"
        
        if monitor_key not in existing_mirror_monitors:
            logger.info(f"\n📍 Creating monitor for mirror {symbol} {side}")
            success = await create_enhanced_monitor(symbol, side, pos, is_mirror=True)
            if success:
                monitors_created += 1
            await asyncio.sleep(0.5)  # Small delay between creations
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ Created {monitors_created} new monitors")
    logger.info("=" * 60)
    
    # Keep the script running to maintain monitor tasks
    if monitors_created > 0:
        logger.info("\n⏳ Keeping monitor tasks running... Press Ctrl+C to stop")
        try:
            await asyncio.Event().wait()  # Wait forever
        except KeyboardInterrupt:
            logger.info("\n⏹️ Stopping monitors...")

if __name__ == "__main__":
    asyncio.run(main())