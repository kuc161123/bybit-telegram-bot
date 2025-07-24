#!/usr/bin/env python3
"""
Rebalance only the unbalanced positions on mirror account
"""

import asyncio
import logging
from typing import Dict, List
from datetime import datetime

from config.settings import (
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
)
from pybit.unified_trading import HTTP
from execution.conservative_rebalancer import ConservativeRebalancer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Positions that need rebalancing on mirror account
POSITIONS_TO_REBALANCE = ['NKNUSDT', 'BIGTIMEUSDT', 'PENDLEUSDT', 'DOTUSDT', 'FLOWUSDT']


class MirrorRebalancer:
    def __init__(self):
        if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
            raise Exception("Mirror trading not enabled")
        
        self.mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        
        # Initialize rebalancer
        self.rebalancer = ConservativeRebalancer()
    
    async def get_positions(self) -> List[Dict]:
        """Get all positions for mirror account"""
        try:
            response = self.mirror_client.get_positions(category="linear", settleCoin="USDT")
            positions = []
            if response.get("retCode") == 0:
                for pos in response.get("result", {}).get("list", []):
                    if float(pos.get('size', 0)) > 0 and pos.get('symbol') in POSITIONS_TO_REBALANCE:
                        positions.append(pos)
            return positions
        except Exception as e:
            logger.error(f"Error getting mirror positions: {e}")
            return []
    
    async def run(self):
        """Main execution"""
        print("=" * 80)
        print("REBALANCING MIRROR ACCOUNT POSITIONS")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Positions to rebalance: {', '.join(POSITIONS_TO_REBALANCE)}")
        print()
        
        # Get positions that need rebalancing
        positions = await self.get_positions()
        
        if not positions:
            print("No positions found that need rebalancing")
            return
        
        print(f"Found {len(positions)} positions to rebalance\n")
        
        # Rebalance each position
        for position in positions:
            symbol = position.get('symbol')
            side = position.get('side')
            size = float(position.get('size', 0))
            
            print(f"Rebalancing {symbol} {side} (Size: {size})...")
            
            try:
                # Check if it needs rebalancing
                needs_rebalance = await self.rebalancer._check_needs_rebalance(position)
                
                if needs_rebalance:
                    # Call the rebalancer
                    result = await self.rebalancer._rebalance_position(position)
                    
                    if result:
                        print(f"✅ Successfully rebalanced {symbol}")
                    else:
                        print(f"⚠️ Failed to rebalance {symbol}")
                else:
                    print(f"✔️ {symbol} is already balanced")
                    
            except Exception as e:
                logger.error(f"❌ Error rebalancing {symbol}: {e}")
            
            # Small delay between positions
            await asyncio.sleep(1)
        
        print("\n" + "=" * 80)
        print("REBALANCING COMPLETE")
        print("=" * 80)
        print("✅ All mirror positions have been processed")


async def main():
    """Entry point"""
    try:
        rebalancer = MirrorRebalancer()
        await rebalancer.run()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())