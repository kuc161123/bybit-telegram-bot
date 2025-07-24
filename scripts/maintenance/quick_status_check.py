#!/usr/bin/env python3
"""
Quick bot status check - shows key metrics
"""
import asyncio
from decimal import Decimal
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def main():
    print("=" * 60)
    print("🤖 BYBIT BOT QUICK STATUS")
    print("=" * 60)
    
    # Check main account
    print("\n📊 MAIN ACCOUNT:")
    response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    if response and response.get('retCode') == 0:
        positions = [p for p in response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        print(f"  Active positions: {len(positions)}")
        for pos in positions:
            print(f"    • {pos['symbol']} {pos['side']}: {pos['size']} contracts")
    
    # Check mirror account
    if is_mirror_trading_enabled():
        print("\n🪞 MIRROR ACCOUNT:")
        response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if response and response.get('retCode') == 0:
            positions = [p for p in response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
            print(f"  Active positions: {len(positions)}")
            for pos in positions:
                print(f"    • {pos['symbol']} {pos['side']}: {pos['size']} contracts")
    
    # Check critical features
    print("\n⚙️ SYSTEM STATUS:")
    from config.settings import ENABLE_ENHANCED_TP_SL
    print(f"  Enhanced TP/SL: {'✅ Enabled' if ENABLE_ENHANCED_TP_SL else '❌ Disabled'}")
    print(f"  Mirror Trading: {'✅ Enabled' if is_mirror_trading_enabled() else '❌ Disabled'}")
    
    # Check monitors
    import pickle
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        enhanced = len(data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {}))
        dashboard = len(data.get('bot_data', {}).get('monitor_tasks', {}))
        print(f"  Enhanced Monitors: {enhanced}")
        print(f"  Dashboard Monitors: {dashboard}")
    except:
        pass
    
    print("\n✅ All key metrics shown above")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())