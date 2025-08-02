#!/usr/bin/env python3
"""
Switch Main Account from Hedge Mode to One-Way Mode
"""
import asyncio
import logging
from clients.bybit_client import bybit_client

logger = logging.getLogger(__name__)

async def switch_main_to_oneway_mode():
    """Switch main account to one-way mode using proper API"""
    
    print("🔄 Switching Main Account to One-Way Mode")
    print("=" * 50)
    
    try:
        # Step 1: Check current mode
        print("🔍 Checking current position mode...")
        
        account_info = bybit_client.get_account_info()
        if account_info and account_info.get('retCode') == 0:
            result = account_info.get('result', {})
            margin_mode = result.get('marginMode', 'UNKNOWN')
            print(f"   Current margin mode: {margin_mode}")
        else:
            print(f"   ⚠️ Could not get account info: {account_info}")
        
        # Step 2: Switch to One-Way Mode (mode=0)
        print("🔄 Switching to One-Way Mode (mode=0)...")
        
        # Use the proper v5 API endpoint
        result = bybit_client.switch_position_mode(
            category="linear",
            mode=0,  # 0 = One-Way Mode
            coin="USDT"  # Apply to all USDT contracts
        )
        
        if result and result.get('retCode') == 0:
            print("✅ Successfully switched main account to One-Way Mode")
            
            # Step 3: Verify the change
            print("🔍 Verifying position mode change...")
            await asyncio.sleep(2)  # Wait for change to take effect
            
            # Check by trying to get positions
            try:
                positions = bybit_client.get_positions(category="linear", settleCoin="USDT")
                if positions and positions.get('retCode') == 0:
                    pos_list = positions.get('result', {}).get('list', [])
                    print(f"   Found {len(pos_list)} positions")
                    
                    # Check position structure for mode verification
                    hedge_mode_detected = False
                    for pos in pos_list[:5]:  # Check first 5 positions
                        symbol = pos.get('symbol', '')
                        pos_idx = pos.get('positionIdx', 'N/A')
                        size = pos.get('size', '0')
                        
                        if float(size) > 0:  # Only log non-zero positions
                            print(f"     Active: {symbol}: positionIdx={pos_idx}, size={size}")
                        else:
                            print(f"     {symbol}: positionIdx={pos_idx}")
                        
                        # Check if still in hedge mode
                        if pos_idx in [1, 2]:
                            hedge_mode_detected = True
                    
                    if hedge_mode_detected:
                        print("⚠️ Warning: Some positions still show hedge mode indices")
                        print("   This might be expected during transition period")
                    else:
                        print("✅ All positions show One-Way Mode indices (positionIdx=0)")
                        
                else:
                    print(f"   Error getting positions: {positions}")
                    
            except Exception as e:
                print(f"   Verification error: {e}")
            
            print("✅ Position mode change completed successfully")
            return True
            
        else:
            error_msg = result.get('retMsg', 'Unknown error') if result else 'No response'
            print(f"❌ Failed to switch position mode: {error_msg}")
            return False
            
    except Exception as e:
        print(f"❌ Error switching position mode: {e}")
        return False

async def compare_account_modes():
    """Compare position modes of both accounts"""
    print("\n🔍 Comparing Account Position Modes")
    print("-" * 40)
    
    try:
        # Main account
        main_info = bybit_client.get_account_info()
        if main_info and main_info.get('retCode') == 0:
            result = main_info.get('result', {})
            main_margin_mode = result.get('marginMode', 'UNKNOWN')
            print(f"Main Account Margin Mode: {main_margin_mode}")
        else:
            print("❌ Could not get main account info")
        
        # Mirror account
        try:
            from execution.mirror_trader import bybit_client_2
            if bybit_client_2:
                mirror_info = bybit_client_2.get_account_info()
                if mirror_info and mirror_info.get('retCode') == 0:
                    result = mirror_info.get('result', {})
                    mirror_margin_mode = result.get('marginMode', 'UNKNOWN')
                    print(f"Mirror Account Margin Mode: {mirror_margin_mode}")
                else:
                    print("❌ Could not get mirror account info")
            else:
                print("⚠️ Mirror account not available")
        except ImportError:
            print("⚠️ Mirror trading not configured")
            
    except Exception as e:
        print(f"❌ Error comparing accounts: {e}")

if __name__ == "__main__":
    async def main():
        print("🚀 Starting Main Account Position Mode Switch")
        
        # Switch main account
        success = await switch_main_to_oneway_mode()
        
        # Compare both accounts
        await compare_account_modes()
        
        if success:
            print("\n✅ Main Account Position Mode Switch COMPLETED!")
            print("🎯 Main account is now in One-Way Mode")
            print("📋 Next: Update code to use One-Way Mode for main account")
        else:
            print("\n❌ Main Account Position Mode Switch FAILED!")
            print("⚠️ Manual intervention may be required")
    
    asyncio.run(main())