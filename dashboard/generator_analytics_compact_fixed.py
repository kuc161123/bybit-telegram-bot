#!/usr/bin/env python3
"""
FIXED Analytics Dashboard - Correct P&L Calculations
This file shows the corrected P&L calculation section
"""

# ... (previous code remains the same until line 209) ...

        # Calculate potential P&L from actual TP/SL orders
        potential_profit_tp1 = 0
        potential_profit_all_tp = 0
        potential_loss_sl = 0

        # CRITICAL FIX: Use monitoring cache instead of direct API call
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            all_orders = await enhanced_tp_sl_manager._get_cached_open_orders("ALL", "main")
        except Exception as e:
            # Fallback to direct API call if cache unavailable
            from clients.bybit_helpers import get_all_open_orders
            all_orders = await get_all_open_orders()

        for pos in active_positions:
            symbol = pos.get('symbol', '')
            position_size = float(pos.get('size', 0))  # This is already the actual size in base units
            avg_price = float(pos.get('avgPrice', 0))
            side = pos.get('side', '')
            leverage = float(pos.get('leverage', 1))

            # FIXED: Remove the incorrect division by leverage
            # The position size from Bybit is already in base units (e.g., 1.0 BTC, not 10.0 BTC for 10x leverage)
            # Only the position VALUE is affected by leverage, not the SIZE

            # Find TP and SL orders for this position
            tp_orders = []
            sl_orders = []

            for order in all_orders:
                if order.get('symbol') == symbol:
                    order_side = order.get('side', '')
                    trigger_by = order.get('triggerBy', '')

                    trigger_price = order.get('triggerPrice', '')
                    reduce_only = order.get('reduceOnly', False)

                    # For positions, we need to identify TP and SL based on trigger price
                    if trigger_price and reduce_only:
                        try:
                            trigger_price_float = float(trigger_price)
                        except (ValueError, TypeError):
                            continue  # Skip orders with invalid trigger prices

                        # TP orders: price is favorable to position
                        if side == 'Buy':
                            # Long position: TP if trigger > avg_price, SL if trigger < avg_price
                            if trigger_price_float > avg_price:
                                tp_orders.append(order)
                            else:
                                sl_orders.append(order)
                        else:  # Sell/Short position
                            # Short position: TP if trigger < avg_price, SL if trigger > avg_price
                            if trigger_price_float < avg_price:
                                tp_orders.append(order)
                            else:
                                sl_orders.append(order)

                    # Also check for regular limit orders that might be TPs
                    elif order.get('orderType') == 'Limit' and reduce_only:
                        # These are likely TP orders
                        tp_orders.append(order)

            # Calculate P&L from actual orders
            if tp_orders:
                # Sort TPs by price (ascending for sell, descending for buy)
                def get_order_price(order):
                    try:
                        trigger_price = order.get('triggerPrice', '')
                        if trigger_price:
                            return float(trigger_price)
                        price = order.get('price', '')
                        if price:
                            return float(price)
                        return 0
                    except (ValueError, TypeError):
                        return 0

                tp_orders.sort(key=get_order_price, reverse=(side == 'Buy'))

                # TP1 profit (FIXED: using actual quantities without dividing by leverage)
                if len(tp_orders) > 0:
                    # For conditional orders, use triggerPrice; for limit orders, use price
                    tp1_order = tp_orders[0]
                    if tp1_order.get('triggerPrice'):
                        tp1_price = float(tp1_order.get('triggerPrice', avg_price))
                    else:
                        tp1_price = float(tp1_order.get('price', avg_price))
                    tp1_qty = float(tp1_order.get('qty', position_size))
                    # FIXED: Use the actual quantity without dividing by leverage

                    if side == 'Buy':
                        # For long positions: profit = (exit_price - entry_price) * size
                        potential_profit_tp1 += (tp1_price - avg_price) * tp1_qty
                    else:
                        # For short positions: profit = (entry_price - exit_price) * size
                        potential_profit_tp1 += (avg_price - tp1_price) * tp1_qty

                # All TPs profit (FIXED: using actual quantities without dividing by leverage)
                for tp_order in tp_orders:
                    # For conditional orders, use triggerPrice; for limit orders, use price
                    if tp_order.get('triggerPrice'):
                        tp_price = float(tp_order.get('triggerPrice', avg_price))
                    else:
                        tp_price = float(tp_order.get('price', avg_price))
                    tp_qty = float(tp_order.get('qty', 0))
                    # FIXED: Use the actual quantity without dividing by leverage

                    if side == 'Buy':
                        # For long positions: profit = (exit_price - entry_price) * size
                        potential_profit_all_tp += (tp_price - avg_price) * tp_qty
                    else:
                        # For short positions: profit = (entry_price - exit_price) * size
                        potential_profit_all_tp += (avg_price - tp_price) * tp_qty

            if sl_orders and len(sl_orders) > 0:
                # Use the first SL order - get trigger price
                sl_order = sl_orders[0]
                sl_price = float(sl_order.get('triggerPrice', 0))
                if sl_price == 0:
                    # Fallback to price field if no trigger price
                    sl_price = float(sl_order.get('price', 0))

                if sl_price > 0:
                    # FIXED: Use actual position size without dividing by leverage

                    if side == 'Buy':
                        # For long positions: loss = (entry_price - exit_price) * position_size
                        potential_loss_sl += abs((avg_price - sl_price) * position_size)
                    else:
                        # For short positions: loss = (exit_price - entry_price) * position_size
                        potential_loss_sl += abs((sl_price - avg_price) * position_size)

        # ... (rest of the code remains the same) ...