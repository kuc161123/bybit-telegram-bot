#!/usr/bin/env python3
"""
Enhanced Conservative Trade Summary
Shows correct TP distribution (85/5/5/5) and comprehensive trade information
"""

def format_enhanced_conservative_summary(
    symbol: str,
    side: str,
    leverage: int,
    margin_amount: float,
    position_size: float,
    trade_group_id: str,
    limit_prices: list,
    tp_prices: list,
    sl_price: float,
    avg_entry: float,
    risk_amount: float,
    max_reward: float,
    execution_time: str,
    mirror_enabled: bool = False,
    mirror_margin: float = 0,
    mirror_size: float = 0,
    errors: list = None
) -> str:
    """
    Create an enhanced conservative trade summary with accurate information
    """

    # Calculate derived values
    position_value = position_size * avg_entry
    risk_reward_ratio = max_reward / risk_amount if risk_amount > 0 else 0

    # Side emoji
    side_emoji = "🟢" if side == "Buy" else "🔴"

    # Build the message
    message = f"""🛡️ <b>CONSERVATIVE TRADE DEPLOYED</b> 🛡️
════════════════════════════════════

📊 <b>{symbol} {side.upper()}</b> │ <code>{leverage}x</code> │ ID: <code>{trade_group_id}</code>
{side_emoji} Market Direction: {"LONG (Bullish)" if side == "Buy" else "SHORT (Bearish)"}

💼 <b>POSITION SUMMARY</b>
├─ Margin Used: <code>${margin_amount:,.2f}</code>
├─ Position Size: <code>{position_size:,.4f}</code> {symbol.replace('USDT', '')}
├─ Position Value: <code>${position_value:,.2f}</code>
"""

    # Add mirror account info if enabled
    if mirror_enabled and mirror_margin > 0:
        message += f"""├─ Mirror Margin: <code>${mirror_margin:,.2f}</code>
├─ Mirror Size: <code>{mirror_size:,.4f}</code> {symbol.replace('USDT', '')}
"""

    message += f"""└─ Entry Strategy: <b>3-Stage Conservative</b>

📍 <b>ENTRY ORDERS</b> (Equal Distribution)
"""

    # Entry order details
    for i, price in enumerate(limit_prices[:3]):
        allocation = 33.3
        order_type = "Market" if i == 0 else f"Limit {i}"
        status = "✅ Placed" if i == 0 else "⏳ Pending"

        if i == 0:
            message += f"├─ Order 1: <code>${price:,.2f}</code> ({allocation:.1f}%) - {order_type} {status}\n"
        elif i == len(limit_prices[:3]) - 1:
            message += f"└─ Order {i+1}: <code>${price:,.2f}</code> ({allocation:.1f}%) - {order_type} {status}\n"
        else:
            message += f"├─ Order {i+1}: <code>${price:,.2f}</code> ({allocation:.1f}%) - {order_type} {status}\n"

    message += f"""
   Average Entry: <code>${avg_entry:,.2f}</code>

🎯 <b>TAKE PROFIT STRATEGY</b> (Updated Distribution)
"""

    # TP order details with CORRECT percentages
    tp_percentages = [85, 5, 5, 5]
    total_profit = 0

    for i, (price, percentage) in enumerate(zip(tp_prices[:4], tp_percentages)):
        distance = ((price - avg_entry) / avg_entry * 100) if side == "Buy" else ((avg_entry - price) / avg_entry * 100)
        tp_value = position_value * (percentage / 100) * (abs(distance) / 100)
        total_profit += tp_value

        emoji = "🎯" if i == 0 else "🏹"

        if i == 0:
            message += f"├─ TP1: <code>${price:,.2f}</code> (+{distance:.2f}%) │ <b>{percentage}%</b> exit │ <code>+${tp_value:,.2f}</code> {emoji}\n"
        elif i == 3:
            message += f"└─ TP4: <code>${price:,.2f}</code> (+{distance:.2f}%) │ <b>{percentage}%</b> exit │ <code>+${tp_value:,.2f}</code> {emoji}\n"
        else:
            message += f"├─ TP{i+1}: <code>${price:,.2f}</code> (+{distance:.2f}%) │ <b>{percentage}%</b> exit │ <code>+${tp_value:,.2f}</code> {emoji}\n"

    message += f"""
   <b>Max Potential Profit: <code>+${max_reward:,.2f}</code></b> 💰

🛡️ <b>RISK MANAGEMENT</b>
├─ Stop Loss: <code>${sl_price:,.2f}</code>
├─ Distance from Entry: {((avg_entry - sl_price) / avg_entry * 100 if side == "Buy" else (sl_price - avg_entry) / avg_entry * 100):.2f}%
├─ Max Risk: <code>-${risk_amount:,.2f}</code>
└─ Risk/Reward Ratio: <b>1:{risk_reward_ratio:.2f}</b> {'🌟' if risk_reward_ratio >= 3 else '✅' if risk_reward_ratio >= 2 else '⚠️'}

📋 <b>TRADE LOGIC EXPLAINED</b>

<b>1. Entry Strategy (3 Orders):</b>
   • 1st order executes immediately at market
   • 2nd & 3rd orders wait at limit prices
   • Equal 33.3% allocation reduces timing risk
   • If price moves favorably, limits may not fill

<b>2. Take Profit Distribution (85/5/5/5):</b>
   • TP1 (85%): Primary exit - locks in bulk profit
   • TP2-4 (5% each): Runners for extended moves
   • Updated from old 70/10/10/10 distribution
   • More conservative, secures profits earlier

<b>3. Risk Protection:</b>
   • Single stop loss protects entire position
   • Calculated for maximum {risk_amount/margin_amount*100:.1f}% account risk
   • Triggers if all entries fill at worst prices

<b>4. Position Management:</b>
   • Monitor tracks fills and adjusts quantities
   • If TP1 hits before all limits fill → cancels remaining limits
   • Automatic rebalancing maintains correct distributions
   • Orphan order cleanup prevents overexposure

🔄 <b>MONITORING FEATURES</b>
├─ Real-time P&L tracking every 8 seconds
├─ Automatic TP/SL order management
├─ Fill detection and quantity adjustments
├─ Smart alerts for key events
└─ Protection against orphaned orders

"""

    # Add mirror trading section if enabled
    if mirror_enabled:
        message += f"""🪞 <b>MIRROR TRADING</b>
├─ Status: {"✅ ACTIVE" if mirror_margin > 0 else "❌ INACTIVE"}
├─ Sync Mode: Real-time order replication
├─ Margin Scaling: {(mirror_margin/margin_amount*100):.1f}% of main
└─ Independent monitoring enabled

"""

    # Add execution summary
    message += f"""⚡ <b>EXECUTION SUMMARY</b>
├─ Setup Time: {execution_time}
├─ Orders Placed: {3 + 4 + 1} (3 entries + 4 TPs + 1 SL)
├─ Network: Mainnet (Live Trading)
└─ Status: Monitoring Active ✅"""

    # Add any warnings
    if errors:
        message += f"\n\n⚠️ <b>WARNINGS:</b>"
        for error in errors:
            message += f"\n• {error}"

    # Add helpful tips
    message += f"""

💡 <b>QUICK TIPS:</b>
• Your position is now being monitored 24/7
• You'll receive alerts for fills, TP hits, and SL triggers
• Use /positions to check real-time P&L
• Use /alerts to manage your notifications
• Consider /stats to track your performance

📱 <b>Next Steps:</b>
1. Monitor dashboard for real-time updates
2. Adjust TP/SL if market conditions change
3. Let the bot manage the position lifecycle"""

    return message


# Example of how to call this function:
if __name__ == "__main__":
    # Test the enhanced summary
    test_summary = format_enhanced_conservative_summary(
        symbol="BTCUSDT",
        side="Buy",
        leverage=10,
        margin_amount=100.0,
        position_size=0.0961,
        trade_group_id="abc123",
        limit_prices=[104000, 103800, 103600],
        tp_prices=[105000, 105500, 106000, 106500],
        sl_price=102500,
        avg_entry=103800,
        risk_amount=50.0,
        max_reward=150.0,
        execution_time="2.34s",
        mirror_enabled=True,
        mirror_margin=50.0,
        mirror_size=0.0481
    )

    print(test_summary)