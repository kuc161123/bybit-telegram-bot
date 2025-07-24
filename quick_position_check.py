#!/usr/bin/env python3
"""
Quick check of positions
"""

from execution.mirror_trader import bybit_client_2

def main():
    print("🔍 Checking mirror positions...")
    
    try:
        response = bybit_client_2.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            
            active_positions = []
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    active_positions.append(pos)
                    
            print(f"\n✅ Found {len(active_positions)} active positions")
            
            # Check for IDUSDT
            idusdt_found = False
            for i, pos in enumerate(active_positions, 1):
                symbol = pos.get('symbol')
                if symbol == 'IDUSDT':
                    idusdt_found = True
                    print(f"\n🎯 IDUSDT FOUND:")
                    print(f"   Size: {pos.get('size')}")
                    print(f"   Side: {pos.get('side')}")
                print(f"{i}. {symbol} - Size: {pos.get('size')}")
                
            if not idusdt_found:
                print("\n❌ IDUSDT NOT FOUND in mirror positions!")
                
        else:
            print(f"❌ API Error: {response}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()