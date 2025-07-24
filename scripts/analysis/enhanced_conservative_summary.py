#!/usr/bin/env python3
"""
Enhanced Conservative Trade Summary Message Generator
Shows detailed, accurate information about Conservative approach trades
"""

def generate_enhanced_conservative_summary(
    symbol: str,
    side: str,
    leverage: int,
    margin_amount: float,
    position_size: float,
    limit_prices: list,
    tp_prices: list,
    sl_price: float,
    avg_entry: float,
    trade_group_id: str,
    limit_order_ids: list,
    tp_order_ids: list,
    sl_order_id: str,
    mirror_enabled: bool = False,
    mirror_margin: float = None,
    mirror_size: float = None
) -> str:
    """Generate an enhanced, detailed Conservative trade summary"""
    
    # Calculate key metrics
    position_value = position_size * avg_entry
    side_text = "LONG" if side == "Buy" else "SHORT"
    side_emoji = "📈" if side == "Buy" else "📉"
    
    # Risk calculations
    if side == "Buy":
        sl_pct = ((avg_entry - sl_price) / avg_entry) * 100
        tp1_pct = ((tp_prices[0] - avg_entry) / avg_entry) * 100
    else:
        sl_pct = ((sl_price - avg_entry) / avg_entry) * 100
        tp1_pct = ((avg_entry - tp_prices[0]) / avg_entry) * 100
    
    risk_amount = position_value * (sl_pct / 100)
    tp1_profit = position_value * 0.85 * (tp1_pct / 100)
    max_profit = sum([
        position_value * 0.85 * (tp1_pct / 100),
        position_value * 0.05 * (((tp_prices[1] - avg_entry) / avg_entry * 100 if side == "Buy" else (avg_entry - tp_prices[1]) / avg_entry * 100) / 100),
        position_value * 0.05 * (((tp_prices[2] - avg_entry) / avg_entry * 100 if side == "Buy" else (avg_entry - tp_prices[2]) / avg_entry * 100) / 100),
        position_value * 0.05 * (((tp_prices[3] - avg_entry) / avg_entry * 100 if side == "Buy" else (avg_entry - tp_prices[3]) / avg_entry * 100) / 100)
    ]) if len(tp_prices) == 4 else tp1_profit
    
    risk_reward = abs(max_profit / risk_amount) if risk_amount != 0 else 0
    
    # Start building message
    message = f"""🛡️ <b>CONSERVATIVE TRADE EXECUTED</b> 🛡️
════════════════════════════════════
{side_emoji} <b>{symbol} {side_text}</b> │ <code>{leverage}x</code> │ ID: <code>{trade_group_id}</code>

💼 <b>POSITION OVERVIEW</b>
├─ Margin Used: <code>${margin_amount:.2f}</code>
├─ Position Size: <code>{position_size:.4f}</code> {symbol.replace('USDT', '')}
├─ Position Value: <code>${position_value:.2f}</code>
└─ Avg Entry Price: <code>${avg_entry:.4f}</code>
"""
    
    # Add mirror info if enabled
    if mirror_enabled and mirror_margin:
        message += f"""
🔄 <b>MIRROR ACCOUNT</b>
├─ Mirror Margin: <code>${mirror_margin:.2f}</code>
├─ Mirror Size: <code>{mirror_size:.4f}</code> {symbol.replace('USDT', '')}
└─ Status: ✅ Synchronized
"""
    
    # Entry strategy section
    message += f"""
📍 <b>ENTRY STRATEGY</b> (3-Stage Conservative)
├─ Limit 1: <code>${limit_prices[0]:.4f}</code> (33.3% • ${position_value/3:.2f})
├─ Limit 2: <code>${limit_prices[1]:.4f}</code> (33.3% • ${position_value/3:.2f})
└─ Limit 3: <code>${limit_prices[2]:.4f}</code> (33.3% • ${position_value/3:.2f})

🎯 <b>TAKE PROFIT LEVELS</b> (85/5/5/5 Distribution)
├─ TP1: <code>${tp_prices[0]:.4f}</code> (+{tp1_pct:.2f}% • 85% exit • ${tp1_profit:.2f})
├─ TP2: <code>${tp_prices[1]:.4f}</code> (5% runner)
├─ TP3: <code>${tp_prices[2]:.4f}</code> (5% runner)  
└─ TP4: <code>${tp_prices[3]:.4f}</code> (5% runner • Max target)

🛡️ <b>RISK MANAGEMENT</b>
├─ Stop Loss: <code>${sl_price:.4f}</code> (-{sl_pct:.2f}%)
├─ Max Risk: <code>${abs(risk_amount):.2f}</code>
├─ Max Reward: <code>${max_profit:.2f}</code>
└─ Risk:Reward: 1:{risk_reward:.1f} {'🌟' if risk_reward >= 3 else '✅' if risk_reward >= 2 else '⚠️'}

📊 <b>ORDER STATUS</b>
├─ Entry Orders: {len(limit_order_ids)}/3 placed ✅
├─ TP Orders: {len(tp_order_ids)}/4 placed {'✅' if len(tp_order_ids) == 4 else '⚠️'}
└─ SL Order: {'✅ Active' if sl_order_id else '❌ Failed'}
"""
    
    # Add explanation of approach
    message += """
📋 <b>TRADE LOGIC EXPLAINED</b>
• <b>Entry:</b> 3 limit orders spread to average entry price
• <b>TP1 (85%):</b> Locks in bulk profit when first target hits
• <b>TP2-4 (5% each):</b> Small runners for extended moves
• <b>After TP1:</b> SL moves to breakeven (risk-free trade)
• <b>Risk Control:</b> Full position protected by stop loss

🔔 <b>POSITION MANAGEMENT</b>
├─ ✅ Auto-monitoring active (10s intervals)
├─ ✅ Order fills tracked automatically
├─ ✅ TP/SL rebalancing on fills
├─ ✅ Breakeven SL after TP1 hit
└─ ✅ Full position tracking until closed
"""
    
    # Add monitoring info
    if len(tp_order_ids) < 4:
        message += f"""
⚠️ <b>NOTICE:</b> Only {len(tp_order_ids)}/4 TP orders placed
└─ Bybit order limit reached. Monitor will manage remaining exits.
"""
    
    # Quick reference
    message += f"""
📌 <b>QUICK REFERENCE</b>
├─ Check Status: /positions
├─ View Stats: /stats
├─ Emergency Close: /emergency
└─ Dashboard: /dashboard

💡 <b>TIP:</b> Conservative approach is ideal for swing trades and trending markets. The 85% TP1 ensures you lock in profits while leaving upside potential."""
    
    return message


# Example usage
if __name__ == "__main__":
    # Test the enhanced summary
    summary = generate_enhanced_conservative_summary(
        symbol="BTCUSDT",
        side="Buy",
        leverage=10,
        margin_amount=100.0,
        position_size=0.0102,
        limit_prices=[98000, 97500, 97000],
        tp_prices=[100000, 101000, 102000, 103000],
        sl_price=96000,
        avg_entry=97500,
        trade_group_id="abc123",
        limit_order_ids=["id1", "id2", "id3"],
        tp_order_ids=["tp1", "tp2", "tp3", "tp4"],
        sl_order_id="sl1",
        mirror_enabled=True,
        mirror_margin=50.0,
        mirror_size=0.0051
    )
    
    print(summary)