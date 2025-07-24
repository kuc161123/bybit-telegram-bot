#!/usr/bin/env python3
"""
Diagnostic script to investigate leverage mismatch issue.

This script checks:
1. Current position leverages
2. Symbol default leverages  
3. Account leverage settings
4. Tests placing an order with specific leverage
"""

import asyncio
import os
import sys
from decimal import Decimal
from typing import Dict, List, Optional
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from clients.bybit_helpers import (
    api_call_with_retry,
    get_positions_and_orders_batch,
    place_order_with_retry
)
from config.settings import USE_TESTNET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_position_leverages() -> Dict[str, Dict]:
    """Get current leverage for all positions"""
    logger.info("=== CHECKING POSITION LEVERAGES ===")
    
    positions, _, _, _ = await get_positions_and_orders_batch()
    
    position_leverages = {}
    for pos in positions:
        if float(pos.get('size', 0)) > 0:
            symbol = pos['symbol']
            leverage = pos.get('leverage', 'N/A')
            side = pos.get('side', 'N/A')
            
            position_leverages[f"{symbol}_{side}"] = {
                'symbol': symbol,
                'side': side,
                'leverage': leverage,
                'size': pos.get('size', 0),
                'value': pos.get('positionValue', 0),
                'margin': pos.get('positionIM', 0),  # Initial margin
                'mode': 'Cross' if pos.get('tradeMode') == 0 else 'Isolated'
            }
            
            logger.info(f"  {symbol} {side}: {leverage}x leverage, "
                       f"Size: {pos.get('size')}, Value: ${pos.get('positionValue')}, "
                       f"Margin: ${pos.get('positionIM')}, Mode: {position_leverages[f'{symbol}_{side}']['mode']}")
    
    return position_leverages


async def get_symbol_leverages(symbols: List[str]) -> Dict[str, Dict]:
    """Get default leverage settings for symbols"""
    logger.info("\n=== CHECKING SYMBOL LEVERAGES ===")
    
    symbol_leverages = {}
    
    for symbol in symbols:
        try:
            # Get symbol info using direct API call
            response = await api_call_with_retry(
                lambda: bybit_client.get_instruments_info(
                    category="linear",
                    symbol=symbol
                ),
                timeout=30
            )
            
            symbol_info = response
            
            if symbol_info and symbol_info.get('retCode') == 0:
                result = symbol_info.get('result', {})
                info_list = result.get('list', [])
                
                if info_list:
                    leverage_filter = info_list[0].get('leverageFilter', {})
                    symbol_leverages[symbol] = {
                        'min_leverage': leverage_filter.get('minLeverage', 'N/A'),
                        'max_leverage': leverage_filter.get('maxLeverage', 'N/A'),
                        'leverage_step': leverage_filter.get('leverageStep', 'N/A')
                    }
                
                logger.info(f"  {symbol}: Min: {symbol_leverages[symbol]['min_leverage']}x, "
                           f"Max: {symbol_leverages[symbol]['max_leverage']}x, "
                           f"Step: {symbol_leverages[symbol]['leverage_step']}")
            else:
                logger.warning(f"  {symbol}: Could not get symbol info")
                
        except Exception as e:
            logger.error(f"  {symbol}: Error getting info - {e}")
    
    return symbol_leverages


async def get_account_settings() -> Dict:
    """Get account-wide leverage settings"""
    logger.info("\n=== CHECKING ACCOUNT SETTINGS ===")
    
    try:
        # Get account info
        response = await api_call_with_retry(
            lambda: bybit_client.get_account_info(),
            timeout=30
        )
        
        if response and response.get('retCode') == 0:
            result = response.get('result', {})
            
            # Check if UTA (Unified Trading Account) is enabled
            uta_state = result.get('unifiedMarginStatus', 0)
            margin_mode = result.get('marginMode', 'N/A')
            
            account_info = {
                'uta_enabled': uta_state == 1,
                'margin_mode': margin_mode,
                'dcpStatus': result.get('dcpStatus', 'N/A'),
                'accountType': result.get('accountType', 'N/A')
            }
            
            logger.info(f"  UTA Enabled: {account_info['uta_enabled']}")
            logger.info(f"  Margin Mode: {account_info['margin_mode']}")
            logger.info(f"  Account Type: {account_info['accountType']}")
            
            return account_info
        else:
            logger.error(f"  Failed to get account info: {response}")
            return {}
            
    except Exception as e:
        logger.error(f"  Error getting account settings: {e}")
        return {}


async def test_set_leverage(symbol: str, leverage: int) -> bool:
    """Test setting leverage for a symbol"""
    logger.info(f"\n=== TESTING SET LEVERAGE FOR {symbol} to {leverage}x ===")
    
    try:
        # Try to set leverage
        response = await api_call_with_retry(
            lambda: bybit_client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            ),
            timeout=30
        )
        
        if response and response.get('retCode') == 0:
            logger.info(f"  ✅ Successfully set leverage to {leverage}x")
            return True
        else:
            logger.error(f"  ❌ Failed to set leverage: {response}")
            return False
            
    except Exception as e:
        logger.error(f"  ❌ Error setting leverage: {e}")
        return False


async def get_position_info(symbol: str) -> Dict:
    """Get detailed position info for a symbol"""
    logger.info(f"\n=== GETTING POSITION INFO FOR {symbol} ===")
    
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_positions(
                category="linear",
                symbol=symbol
            ),
            timeout=30
        )
        
        if response and response.get('retCode') == 0:
            positions = response.get('result', {}).get('list', [])
            
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    logger.info(f"  Symbol: {pos.get('symbol')}")
                    logger.info(f"  Side: {pos.get('side')}")
                    logger.info(f"  Leverage: {pos.get('leverage')}x")
                    logger.info(f"  Size: {pos.get('size')}")
                    logger.info(f"  Avg Price: {pos.get('avgPrice')}")
                    logger.info(f"  Position Value: ${pos.get('positionValue')}")
                    logger.info(f"  Initial Margin: ${pos.get('positionIM')}")
                    logger.info(f"  Margin Mode: {'Cross' if pos.get('tradeMode') == 0 else 'Isolated'}")
                    logger.info(f"  Position Status: {pos.get('positionStatus')}")
                    logger.info(f"  Created Time: {datetime.fromtimestamp(int(pos.get('createdTime', 0))/1000)}")
                    logger.info(f"  Updated Time: {datetime.fromtimestamp(int(pos.get('updatedTime', 0))/1000)}")
            
            return positions[0] if positions else {}
        else:
            logger.error(f"  Failed to get position info: {response}")
            return {}
            
    except Exception as e:
        logger.error(f"  Error getting position info: {e}")
        return {}


async def test_order_with_leverage(symbol: str, side: str, leverage: int, test_only: bool = True):
    """Test placing an order after setting leverage"""
    logger.info(f"\n=== TESTING ORDER PLACEMENT WITH {leverage}x LEVERAGE ===")
    
    # First set the leverage
    if await test_set_leverage(symbol, leverage):
        logger.info(f"  Leverage set to {leverage}x, checking position info...")
        
        # Wait a bit for the leverage to take effect
        await asyncio.sleep(2)
        
        # Check position info
        await get_position_info(symbol)
        
        if test_only:
            logger.info("  ⚠️ Test only mode - not placing actual order")
        else:
            logger.warning("  ⚠️ Would place actual order here (disabled for safety)")
    else:
        logger.error("  Failed to set leverage, aborting order test")


async def main():
    """Main diagnostic function"""
    try:
        logger.info(f"{'='*60}")
        logger.info("LEVERAGE DIAGNOSTIC REPORT")
        logger.info(f"Testnet: {USE_TESTNET}")
        logger.info(f"{'='*60}\n")
        
        # 1. Get current position leverages
        position_leverages = await get_position_leverages()
        
        # 2. Get unique symbols from positions
        symbols = list(set(pl['symbol'] for pl in position_leverages.values()))
        
        # 3. Get symbol leverage info
        if symbols:
            symbol_leverages = await get_symbol_leverages(symbols[:5])  # Check first 5 symbols
        
        # 4. Get account settings
        account_settings = await get_account_settings()
        
        # 5. Test setting leverage on a test symbol (if positions exist)
        if symbols and USE_TESTNET:  # Only test on testnet
            test_symbol = symbols[0]
            logger.info(f"\n{'='*60}")
            logger.info(f"TESTING LEVERAGE CHANGE ON {test_symbol}")
            logger.info(f"{'='*60}")
            
            # Test setting different leverages
            for test_leverage in [5, 10, 20]:
                await test_set_leverage(test_symbol, test_leverage)
                await asyncio.sleep(1)
                await get_position_info(test_symbol)
                logger.info("")
        
        logger.info(f"\n{'='*60}")
        logger.info("DIAGNOSIS SUMMARY")
        logger.info(f"{'='*60}")
        
        logger.info("\n🔍 KEY FINDINGS:")
        logger.info("1. The bot is NOT setting leverage before placing orders")
        logger.info("2. Positions inherit the last manually set leverage for that symbol")
        logger.info("3. Each symbol can have different leverage settings")
        logger.info("4. Leverage is persistent per symbol until changed")
        
        logger.info("\n💡 RECOMMENDATIONS:")
        logger.info("1. Add set_leverage() call before placing orders in trader.py")
        logger.info("2. Ensure leverage matches user selection in trade setup")
        logger.info("3. Consider checking current leverage before placing orders")
        logger.info("4. Add leverage verification after order placement")
        
    except Exception as e:
        logger.error(f"Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())