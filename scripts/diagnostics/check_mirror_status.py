#!/usr/bin/env python3
"""Check mirror account status"""

import asyncio
from execution.mirror_trader import (
    get_mirror_open_orders_direct,
    get_mirror_positions,
    is_mirror_trading_enabled
)

async def check_mirror_properly():
    print('🔍 MIRROR ACCOUNT STATUS CHECK:')
    print('='*70)
    
    if not is_mirror_trading_enabled():
        print('❌ Mirror trading is not enabled')
        return
    
    try:
        # Get mirror positions
        positions = await get_mirror_positions()
        
        # Get mirror orders
        orders = await get_mirror_open_orders_direct()
        
        # Check conservative positions
        conservative_symbols = ['INJUSDT', 'JUPUSDT', 'IOTXUSDT']
        
        print(f'Found {len(positions)} positions and {len(orders)} orders on mirror account')
        print()
        
        for symbol in conservative_symbols:
            # Find position
            position = next((p for p in positions if p.get('symbol') == symbol and float(p.get('size', 0)) > 0), None)
            
            if position:
                size = float(position.get('size', 0))
                side = position.get('side')
                
                # Count orders
                symbol_orders = [o for o in orders if o.get('symbol') == symbol]
                tp_count = sum(1 for o in symbol_orders if 'TP' in o.get('orderLinkId', '') and o.get('reduceOnly'))
                sl_count = sum(1 for o in symbol_orders if 'SL' in o.get('orderLinkId', '') and o.get('reduceOnly'))
                limit_count = sum(1 for o in symbol_orders if o.get('orderType') == 'Limit' and not o.get('reduceOnly'))
                
                status = '✅' if tp_count == 4 and sl_count == 1 else '❌'
                print(f'{status} {symbol} (MIRROR):')
                print(f'   Position: {size} ({side})')
                print(f'   Orders: {tp_count} TPs, {sl_count} SL, {limit_count} limits')
                
                if tp_count != 4 or sl_count != 1:
                    print(f'   ⚠️  NEEDS REBALANCING!')
                print()
            else:
                print(f'❌ {symbol} (MIRROR): No position found')
                print()
                
    except Exception as e:
        print(f'❌ Error checking mirror account: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_mirror_properly())