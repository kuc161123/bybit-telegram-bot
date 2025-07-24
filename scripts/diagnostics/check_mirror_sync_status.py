#!/usr/bin/env python3
"""
Check Mirror Sync Status

Compares positions between main and mirror accounts to identify sync issues
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client as bybit_client_1
from config.settings import ENABLE_MIRROR_TRADING

# Set up logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mirror_sync_status.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Try to import mirror client
try:
    from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
    MIRROR_AVAILABLE = True
except ImportError:
    logger.warning("Mirror trading not available")
    MIRROR_AVAILABLE = False
    bybit_client_2 = None

async def get_all_positions(client, account_name: str) -> Dict[str, Dict]:
    """Get all positions for an account"""
    try:
        all_positions = {}
        cursor = ""
        
        while True:
            params = {
                "category": "linear",
                "settleCoin": "USDT",
                "limit": 200
            }
            
            if cursor:
                params["cursor"] = cursor
            
            response = client.get_positions(**params)
            
            if response['retCode'] == 0:
                positions = response['result']['list']
                
                for pos in positions:
                    if float(pos['size']) > 0:
                        symbol = pos['symbol']
                        side = pos['side']
                        key = f"{symbol}_{side}"
                        
                        all_positions[key] = {
                            'symbol': symbol,
                            'side': side,
                            'size': Decimal(pos['size']),
                            'avgPrice': Decimal(pos['avgPrice']),
                            'unrealisedPnl': Decimal(pos['unrealisedPnl']),
                            'cumRealisedPnl': Decimal(pos['cumRealisedPnl']),
                            'markPrice': Decimal(pos['markPrice']),
                            'positionIdx': int(pos['positionIdx']),
                            'positionValue': Decimal(pos['positionValue'])
                        }
                
                # Check if there are more pages
                cursor = response['result'].get('nextPageCursor', '')
                if not cursor:
                    break
            else:
                logger.error(f"Error fetching {account_name} positions: {response.get('retMsg')}")
                break
        
        return all_positions
        
    except Exception as e:
        logger.error(f"Error getting {account_name} positions: {e}")
        return {}

async def get_active_orders(client, symbol: str, account_name: str) -> List[Dict]:
    """Get active orders for a symbol"""
    try:
        response = client.get_open_orders(
            category="linear",
            symbol=symbol,
            limit=50
        )
        
        if response['retCode'] == 0:
            return response['result']['list']
        else:
            logger.error(f"Error fetching {account_name} orders for {symbol}: {response.get('retMsg')}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting {account_name} orders for {symbol}: {e}")
        return []

async def check_position_mode(client, account_name: str) -> str:
    """Check position mode for account"""
    try:
        # Get a position to check its mode
        response = client.get_positions(
            category="linear",
            settleCoin="USDT",
            limit=1
        )
        
        if response['retCode'] == 0 and response['result']['list']:
            # Check positionIdx: 0 = One-way mode, 1/2 = Hedge mode
            pos_idx = int(response['result']['list'][0]['positionIdx'])
            mode = "One-way" if pos_idx == 0 else "Hedge"
            return mode
        else:
            return "One-way"  # Default assumption
            
    except Exception as e:
        logger.error(f"Error checking {account_name} position mode: {e}")
        return "Unknown"

async def main():
    """Main check function"""
    logger.info("=" * 80)
    logger.info("🔍 MIRROR SYNC STATUS CHECK")
    logger.info("=" * 80)
    
    # Check if mirror trading is enabled
    if not ENABLE_MIRROR_TRADING:
        logger.warning("⚠️ Mirror trading is DISABLED in settings")
        return
    
    if not MIRROR_AVAILABLE or not bybit_client_2:
        logger.error("❌ Mirror client not available")
        return
    
    # Get positions for both accounts
    logger.info("\n📊 Fetching Main Account Positions...")
    main_positions = await get_all_positions(bybit_client_1, "Main")
    
    logger.info("\n📊 Fetching Mirror Account Positions...")
    mirror_positions = await get_all_positions(bybit_client_2, "Mirror")
    
    # Check position modes
    logger.info("\n🔧 Checking Position Modes...")
    main_mode = await check_position_mode(bybit_client_1, "Main")
    mirror_mode = await check_position_mode(bybit_client_2, "Mirror")
    
    logger.info(f"Main Account Mode: {main_mode}")
    logger.info(f"Mirror Account Mode: {mirror_mode}")
    
    if main_mode != mirror_mode:
        logger.warning("⚠️ Position modes don't match! This will cause sync issues.")
    
    # Compare positions
    logger.info("\n📊 POSITION COMPARISON")
    logger.info("-" * 80)
    
    all_keys = set(main_positions.keys()) | set(mirror_positions.keys())
    
    matched = 0
    mismatched = 0
    main_only = 0
    mirror_only = 0
    
    for key in sorted(all_keys):
        main_pos = main_positions.get(key)
        mirror_pos = mirror_positions.get(key)
        
        if main_pos and mirror_pos:
            # Both have position
            main_size = main_pos['size']
            mirror_size = mirror_pos['size']
            
            # Check if sizes match (within 0.1% tolerance)
            size_diff = abs(main_size - mirror_size)
            tolerance = main_size * Decimal('0.001')
            
            if size_diff <= tolerance:
                matched += 1
                logger.info(f"✅ {key}: Main={main_size} Mirror={mirror_size} [MATCHED]")
            else:
                mismatched += 1
                diff_pct = (size_diff / main_size * 100) if main_size > 0 else 0
                logger.warning(f"⚠️ {key}: Main={main_size} Mirror={mirror_size} [MISMATCH {diff_pct:.2f}%]")
                
                # Get orders for mismatched positions
                symbol = key.split('_')[0]
                main_orders = await get_active_orders(bybit_client_1, symbol, "Main")
                mirror_orders = await get_active_orders(bybit_client_2, symbol, "Mirror")
                
                logger.info(f"   Main Orders: {len(main_orders)} (TP: {sum(1 for o in main_orders if o.get('orderType') == 'TakeProfit')}, SL: {sum(1 for o in main_orders if o.get('orderType') == 'StopLoss')})")
                logger.info(f"   Mirror Orders: {len(mirror_orders)} (TP: {sum(1 for o in mirror_orders if o.get('orderType') == 'TakeProfit')}, SL: {sum(1 for o in mirror_orders if o.get('orderType') == 'StopLoss')})")
                
        elif main_pos and not mirror_pos:
            main_only += 1
            logger.error(f"❌ {key}: Main={main_pos['size']} Mirror=None [MAIN ONLY]")
            
        elif not main_pos and mirror_pos:
            mirror_only += 1
            logger.error(f"❌ {key}: Main=None Mirror={mirror_pos['size']} [MIRROR ONLY]")
    
    # Summary
    logger.info("\n📊 SUMMARY")
    logger.info("-" * 80)
    logger.info(f"Total Main Positions: {len(main_positions)}")
    logger.info(f"Total Mirror Positions: {len(mirror_positions)}")
    logger.info(f"Matched Positions: {matched}")
    logger.info(f"Mismatched Sizes: {mismatched}")
    logger.info(f"Main Only: {main_only}")
    logger.info(f"Mirror Only: {mirror_only}")
    
    # Check account balances
    logger.info("\n💰 Account Balances")
    try:
        main_balance = bybit_client_1.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        if main_balance['retCode'] == 0:
            main_equity = main_balance['result']['list'][0]['totalEquity']
            main_available = main_balance['result']['list'][0]['totalAvailableBalance']
            logger.info(f"Main Account: Equity=${main_equity}, Available=${main_available}")
    except:
        pass
    
    try:
        mirror_balance = bybit_client_2.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        if mirror_balance['retCode'] == 0:
            mirror_equity = mirror_balance['result']['list'][0]['totalEquity']
            mirror_available = mirror_balance['result']['list'][0]['totalAvailableBalance']
            logger.info(f"Mirror Account: Equity=${mirror_equity}, Available=${mirror_available}")
    except:
        pass
    
    # Recommendations
    logger.info("\n💡 RECOMMENDATIONS")
    logger.info("-" * 80)
    
    if main_mode != mirror_mode:
        logger.info("1. ⚠️ Set both accounts to the same position mode (One-way recommended)")
    
    if main_only > 0:
        logger.info("2. ❌ Mirror account is missing positions - need to open matching positions")
    
    if mirror_only > 0:
        logger.info("3. ❌ Mirror account has extra positions - need to close unmatched positions")
    
    if mismatched > 0:
        logger.info("4. ⚠️ Some positions have size mismatches - may need manual adjustment")
    
    if matched == len(main_positions) and matched == len(mirror_positions) and main_mode == mirror_mode:
        logger.info("✅ Accounts are fully synchronized!")

if __name__ == "__main__":
    asyncio.run(main())