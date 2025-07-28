#!/usr/bin/env python3
"""
EMERGENCY: Create missing SL orders immediately for unprotected positions
Extract original SL parameters from trading logs and recreate them
"""
import asyncio
import os
import sys
import re
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_instrument_info, get_correct_position_idx
from utils.helpers import value_adjusted_to_step
from pybit.unified_trading import HTTP

def extract_original_sl_from_logs() -> Dict[str, Dict]:
    """Extract original SL order parameters from trading logs"""
    log_file = 'trading_bot.log'
    if not os.path.exists(log_file):
        print(f"❌ Log file {log_file} not found")
        return {}
    
    sl_data = {}  # position_key -> sl_info
    
    print("📖 Extracting original SL parameters from logs...")
    
    with open(log_file, 'r') as f:
        for line in f:
            # Look for SL placement patterns
            if any(pattern in line for pattern in [
                'SL placed', 'SL order', 'Stop Loss', 'placed SL', 'SL created'
            ]):
                # Extract timestamp
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not timestamp_match:
                    continue
                
                timestamp = timestamp_match.group(1)
                message = line[timestamp_match.end():].strip()
                
                # Extract symbol
                symbol_match = re.search(r'([A-Z]{3,}USDT)', message)
                if not symbol_match:
                    continue
                
                symbol = symbol_match.group(1)
                
                # Extract side
                side_match = re.search(r'(Buy|Sell)', message, re.IGNORECASE)
                if not side_match:
                    continue
                
                side = side_match.group(1)
                
                # Determine account
                account = 'main'
                if 'MIRROR' in message or 'mirror' in message or '🪞' in message:
                    account = 'mirror'
                
                position_key = f"{symbol}_{side}_{account}"
                
                # Extract SL price
                sl_price_match = re.search(r'(?:SL|Stop|stop).*?(?:@|at|price).*?(\d+\.?\d*)', message, re.IGNORECASE)
                if sl_price_match:
                    sl_price = Decimal(sl_price_match.group(1))
                    
                    # Extract quantity if available
                    qty_match = re.search(r'(?:qty|quantity|size).*?(\d+\.?\d*)', message, re.IGNORECASE)
                    sl_qty = Decimal(qty_match.group(1)) if qty_match else None
                    
                    sl_data[position_key] = {
                        'symbol': symbol,
                        'side': side,
                        'account': account,
                        'sl_price': sl_price,
                        'sl_qty': sl_qty,
                        'timestamp': timestamp,
                        'message': message
                    }
    
    return sl_data

def calculate_emergency_sl_price(symbol: str, side: str, current_price: Decimal, entry_price: Decimal = None) -> Decimal:
    """Calculate emergency SL price based on risk management rules"""
    
    # Standard risk levels by symbol type
    risk_percentages = {
        'BTCUSDT': Decimal('3.0'),   # 3% for BTC
        'ETHUSDT': Decimal('4.0'),   # 4% for ETH
        'default': Decimal('5.0')    # 5% for altcoins
    }
    
    # Get risk percentage for this symbol
    if symbol in risk_percentages:
        risk_pct = risk_percentages[symbol]
    else:
        risk_pct = risk_percentages['default']
    
    # Calculate SL price based on position side
    if side.upper() == 'SELL':
        # Short position - SL above current price
        sl_price = current_price * (Decimal('100') + risk_pct) / Decimal('100')
    else:
        # Long position - SL below current price
        sl_price = current_price * (Decimal('100') - risk_pct) / Decimal('100')
    
    return sl_price

async def place_sl_order(client: HTTP, symbol: str, side: str, qty: str, sl_price: str, account_type: str) -> Tuple[bool, str, Dict]:
    """Place a stop loss order"""
    try:
        # SL orders are same side as position (to close the position)
        # Get position index for hedge mode
        position_idx = await get_correct_position_idx(symbol, side)
        
        # Generate order link ID
        order_link_id = f"{account_type[:1].upper()}SL_{symbol}_{int(time.time())}"
        
        # Place stop market order
        result = client.place_order(
            category="linear",
            symbol=symbol,
            side=side,  # Same side as position
            orderType="Market",
            qty=qty,
            reduceOnly=True,
            orderLinkId=order_link_id,
            timeInForce="IOC",
            stopOrderType="Stop",
            triggerPrice=sl_price,
            triggerBy="LastPrice",
            positionIdx=position_idx
        )
        
        if result.get('retCode') == 0:
            order_result = result.get('result', {})
            return True, "SL order placed successfully", order_result
        else:
            error_msg = result.get('retMsg', 'Unknown error')
            return False, f"Failed to place SL: {error_msg}", {}
    
    except Exception as e:
        return False, f"Exception placing SL: {str(e)}", {}

async def create_missing_sl_orders():
    """Create SL orders for all unprotected positions"""
    print("🚨 EMERGENCY: Creating Missing SL Orders")
    print("=" * 50)
    
    # Get configuration
    config = {
        'TESTNET': os.getenv('TESTNET', 'false').lower() == 'true',
        'BYBIT_API_KEY': os.getenv('BYBIT_API_KEY'),
        'BYBIT_API_SECRET': os.getenv('BYBIT_API_SECRET'),
        'ENABLE_MIRROR_TRADING': os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true',
        'BYBIT_API_KEY_2': os.getenv('BYBIT_API_KEY_2'),
        'BYBIT_API_SECRET_2': os.getenv('BYBIT_API_SECRET_2')
    }
    
    # Initialize clients
    main_client = HTTP(
        testnet=config['TESTNET'],
        api_key=config['BYBIT_API_KEY'],
        api_secret=config['BYBIT_API_SECRET']
    )
    
    mirror_client = None
    if config['ENABLE_MIRROR_TRADING']:
        mirror_client = HTTP(
            testnet=config['TESTNET'],
            api_key=config['BYBIT_API_KEY_2'],
            api_secret=config['BYBIT_API_SECRET_2']
        )
    
    # Extract original SL data from logs
    original_sl_data = extract_original_sl_from_logs()
    print(f"📖 Found {len(original_sl_data)} SL references in logs")
    
    # Get current positions that need SL orders
    positions_needing_sl = [
        # Main account positions (all missing SL)
        {'account': 'main', 'client': main_client, 'positions': []},
        {'account': 'mirror', 'client': mirror_client, 'positions': []} if mirror_client else None
    ]
    
    # Remove None entry
    positions_needing_sl = [p for p in positions_needing_sl if p is not None]
    
    # Get positions for each account
    for account_info in positions_needing_sl:
        account = account_info['account']
        client = account_info['client']
        
        if not client:
            continue
        
        # Get all positions
        all_positions = await get_all_positions(client=client)
        
        for pos in all_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = pos.get('size')
                avg_price = pos.get('avgPrice', '0')
                mark_price = pos.get('markPrice', avg_price)
                
                # Only add main account positions (since they're all missing SL)
                # or mirror positions that we know are missing SL
                if account == 'main' or (account == 'mirror' and symbol == 'DYDXUSDT'):
                    account_info['positions'].append({
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'avg_price': Decimal(str(avg_price)) if avg_price != '0' else None,
                        'mark_price': Decimal(str(mark_price)) if mark_price != '0' else None
                    })
    
    # Create SL orders
    total_positions = sum(len(account_info['positions']) for account_info in positions_needing_sl)
    successful_sl_created = 0
    
    print(f"🎯 Creating SL orders for {total_positions} unprotected positions...")
    
    for account_info in positions_needing_sl:
        account = account_info['account']
        client = account_info['client']
        positions = account_info['positions']
        
        if not positions:
            continue
        
        print(f"\n🏠 {'MAIN' if account == 'main' else 'MIRROR'} ACCOUNT - {len(positions)} positions")
        print("-" * 40)
        
        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            size = pos['size']
            avg_price = pos['avg_price']
            mark_price = pos['mark_price']
            
            position_key = f"{symbol}_{side}_{account}"
            
            print(f"\n📊 {position_key}:")
            print(f"   Size: {size}")
            print(f"   Avg Price: {avg_price}")
            print(f"   Mark Price: {mark_price}")
            
            # Determine SL price
            current_price = mark_price or avg_price
            if not current_price:
                print(f"   ❌ Cannot determine current price - skipping")
                continue
            
            # Check if we have original SL data from logs
            if position_key in original_sl_data:
                sl_price = original_sl_data[position_key]['sl_price']
                print(f"   📖 Using original SL price from logs: {sl_price}")
            else:
                # Calculate emergency SL price
                sl_price = calculate_emergency_sl_price(symbol, side, current_price, avg_price)
                print(f"   🚨 Calculated emergency SL price: {sl_price}")
            
            # Get instrument info for quantity validation
            try:
                instrument_info = await get_instrument_info(symbol)
                if instrument_info:
                    lot_size_filter = instrument_info.get("lotSizeFilter", {})
                    qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
                    min_order_qty = Decimal(lot_size_filter.get("minOrderQty", "0.001"))
                    
                    # Adjust SL quantity to step size
                    sl_qty = value_adjusted_to_step(Decimal(str(size)), qty_step)
                    
                    if sl_qty < min_order_qty:
                        print(f"   ❌ SL quantity {sl_qty} below minimum {min_order_qty}")
                        continue
                else:
                    # Fallback
                    sl_qty = Decimal(str(size))
                
            except Exception as e:
                print(f"   ⚠️ Could not get instrument info: {e}")
                sl_qty = Decimal(str(size))
            
            # Adjust SL price to tick size if available
            try:
                if instrument_info:
                    price_filter = instrument_info.get("priceFilter", {})
                    tick_size = Decimal(price_filter.get("tickSize", "0.0001"))
                    sl_price = value_adjusted_to_step(sl_price, tick_size)
            except:
                pass
            
            print(f"   📤 Placing SL order: {side} {sl_qty} @ {sl_price}")
            
            # Place SL order
            success, message, result = await place_sl_order(
                client, symbol, side, str(sl_qty), str(sl_price), account
            )
            
            if success:
                order_id = result.get('orderId', 'Unknown')
                print(f"   ✅ SL created successfully: {order_id[:8]}...")
                successful_sl_created += 1
            else:
                print(f"   ❌ SL creation failed: {message}")
            
            # Small delay between orders
            await asyncio.sleep(0.5)
    
    # Summary
    print(f"\n🎯 EMERGENCY SL CREATION COMPLETE")
    print(f"Total positions processed: {total_positions}")
    print(f"SL orders created: {successful_sl_created}")
    print(f"Success rate: {(successful_sl_created/total_positions)*100:.1f}%" if total_positions > 0 else "No positions")
    
    if successful_sl_created < total_positions:
        failed_count = total_positions - successful_sl_created
        print(f"\n⚠️ {failed_count} SL orders failed to create")
        print(f"Please check these positions manually and create SL orders")
    
    print(f"\n📋 RISK MANAGEMENT STATUS:")
    print(f"✅ Positions now protected with SL: {successful_sl_created}")
    print(f"❌ Positions still unprotected: {total_positions - successful_sl_created}")
    
    return {
        'total_positions': total_positions,
        'successful_sl_created': successful_sl_created,
        'original_sl_data': original_sl_data
    }

if __name__ == "__main__":
    asyncio.run(create_missing_sl_orders())