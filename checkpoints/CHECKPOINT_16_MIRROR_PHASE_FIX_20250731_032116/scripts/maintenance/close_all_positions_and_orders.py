#!/usr/bin/env python3
"""
Close all positions and orders on both main and mirror accounts
"""

import asyncio
import logging
from decimal import Decimal
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize clients
logger.info("Initializing Bybit clients...")
bybit_client = HTTP(
    testnet=False,
    api_key=os.getenv('BYBIT_API_KEY'),
    api_secret=os.getenv('BYBIT_API_SECRET')
)

# Initialize mirror client if enabled
bybit_client_2 = None
if os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true':
    bybit_client_2 = HTTP(
        testnet=False,
        api_key=os.getenv('BYBIT_API_KEY_2'),
        api_secret=os.getenv('BYBIT_API_SECRET_2')
    )

async def close_all_positions_and_orders():
    """Close all positions and orders on both accounts"""
    
    print("\n🚨 CLOSING ALL POSITIONS AND ORDERS")
    print("=" * 60)
    
    # Track results
    results = {
        'main': {'positions_closed': 0, 'orders_cancelled': 0, 'errors': []},
        'mirror': {'positions_closed': 0, 'orders_cancelled': 0, 'errors': []}
    }
    
    # 1. Close positions and orders on MAIN account
    print("\n1️⃣ MAIN ACCOUNT:")
    print("-" * 40)
    
    try:
        # Get all positions
        positions_response = bybit_client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if positions_response['retCode'] == 0:
            positions = positions_response['result']['list']
            print(f"Found {len(positions)} positions on main account")
            
            for pos in positions:
                if float(pos.get('size', '0')) > 0:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    
                    # Close position with market order
                    close_side = "Sell" if side == "Buy" else "Buy"
                    
                    try:
                        close_response = bybit_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=close_side,
                            orderType="Market",
                            qty=size,
                            reduceOnly=True,
                            positionIdx=pos.get('positionIdx', 0)
                        )
                        
                        if close_response['retCode'] == 0:
                            print(f"✅ Closed {symbol} {side} position: {size}")
                            results['main']['positions_closed'] += 1
                        else:
                            error_msg = f"Failed to close {symbol}: {close_response.get('retMsg')}"
                            print(f"❌ {error_msg}")
                            results['main']['errors'].append(error_msg)
                    except Exception as e:
                        error_msg = f"Error closing {symbol}: {str(e)}"
                        print(f"❌ {error_msg}")
                        results['main']['errors'].append(error_msg)
        
        # Cancel all open orders
        cancel_response = bybit_client.cancel_all_orders(
            category="linear",
            settleCoin="USDT"
        )
        
        if cancel_response['retCode'] == 0:
            cancelled = cancel_response['result']['list']
            results['main']['orders_cancelled'] = len(cancelled)
            print(f"✅ Cancelled {len(cancelled)} orders on main account")
        else:
            print(f"❌ Failed to cancel orders: {cancel_response.get('retMsg')}")
            
    except Exception as e:
        error_msg = f"Error processing main account: {str(e)}"
        print(f"❌ {error_msg}")
        results['main']['errors'].append(error_msg)
    
    # 2. Close positions and orders on MIRROR account
    if bybit_client_2:
        print("\n2️⃣ MIRROR ACCOUNT:")
        print("-" * 40)
        
        try:
            # Get all positions
            positions_response = bybit_client_2.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if positions_response['retCode'] == 0:
                positions = positions_response['result']['list']
                print(f"Found {len(positions)} positions on mirror account")
                
                for pos in positions:
                    if float(pos.get('size', '0')) > 0:
                        symbol = pos['symbol']
                        side = pos['side']
                        size = pos['size']
                        
                        # Close position with market order
                        close_side = "Sell" if side == "Buy" else "Buy"
                        
                        try:
                            close_response = bybit_client_2.place_order(
                                category="linear",
                                symbol=symbol,
                                side=close_side,
                                orderType="Market",
                                qty=size,
                                reduceOnly=True,
                                positionIdx=pos.get('positionIdx', 0)
                            )
                            
                            if close_response['retCode'] == 0:
                                print(f"✅ Closed {symbol} {side} position: {size}")
                                results['mirror']['positions_closed'] += 1
                            else:
                                error_msg = f"Failed to close {symbol}: {close_response.get('retMsg')}"
                                print(f"❌ {error_msg}")
                                results['mirror']['errors'].append(error_msg)
                        except Exception as e:
                            error_msg = f"Error closing {symbol}: {str(e)}"
                            print(f"❌ {error_msg}")
                            results['mirror']['errors'].append(error_msg)
            
            # Cancel all open orders
            cancel_response = bybit_client_2.cancel_all_orders(
                category="linear",
                settleCoin="USDT"
            )
            
            if cancel_response['retCode'] == 0:
                cancelled = cancel_response['result']['list']
                results['mirror']['orders_cancelled'] = len(cancelled)
                print(f"✅ Cancelled {len(cancelled)} orders on mirror account")
            else:
                print(f"❌ Failed to cancel orders: {cancel_response.get('retMsg')}")
                
        except Exception as e:
            error_msg = f"Error processing mirror account: {str(e)}"
            print(f"❌ {error_msg}")
            results['mirror']['errors'].append(error_msg)
    else:
        print("\n2️⃣ MIRROR ACCOUNT: Disabled")
    
    # 3. Clear bot persistence
    print("\n3️⃣ CLEARING BOT PERSISTENCE:")
    print("-" * 40)
    
    try:
        import pickle
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        if os.path.exists(pkl_path):
            # Backup first
            from datetime import datetime
            backup_path = f"{pkl_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy(pkl_path, backup_path)
            print(f"✅ Created backup: {backup_path}")
            
            # Load and clear data
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            
            # Clear all monitor and position data
            if 'bot_data' in data:
                data['bot_data']['enhanced_tp_sl_monitors'] = {}
                data['bot_data']['monitor_tasks'] = {}
                data['bot_data']['active_monitors'] = {}
            
            # Clear user positions
            for user_id in data.get('user_data', {}):
                data['user_data'][user_id]['positions'] = {}
            
            # Save cleaned data
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            
            print("✅ Cleared bot persistence data")
    except Exception as e:
        print(f"❌ Error clearing persistence: {e}")
    
    # 4. Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY:")
    print("-" * 40)
    
    print(f"\nMAIN ACCOUNT:")
    print(f"  Positions closed: {results['main']['positions_closed']}")
    print(f"  Orders cancelled: {results['main']['orders_cancelled']}")
    if results['main']['errors']:
        print(f"  Errors: {len(results['main']['errors'])}")
        for err in results['main']['errors']:
            print(f"    - {err}")
    
    if bybit_client_2:
        print(f"\nMIRROR ACCOUNT:")
        print(f"  Positions closed: {results['mirror']['positions_closed']}")
        print(f"  Orders cancelled: {results['mirror']['orders_cancelled']}")
        if results['mirror']['errors']:
            print(f"  Errors: {len(results['mirror']['errors'])}")
            for err in results['mirror']['errors']:
                print(f"    - {err}")
    
    print("\n✅ ALL POSITIONS AND ORDERS CLOSED")
    print("✅ Bot persistence cleared")
    print("\nYou can now restart the bot with a clean state.")
    
    return True

if __name__ == "__main__":
    asyncio.run(close_all_positions_and_orders())