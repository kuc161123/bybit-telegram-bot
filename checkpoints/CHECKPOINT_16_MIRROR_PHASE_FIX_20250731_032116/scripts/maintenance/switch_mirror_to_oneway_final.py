#!/usr/bin/env python3
"""
Switch Mirror Account from Hedge Mode to One-Way Mode
Using proper Bybit API v5 endpoint
"""
import asyncio
import logging
from clients.bybit_client import bybit_client

try:
    from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
    MIRROR_AVAILABLE = True
except ImportError:
    MIRROR_AVAILABLE = False
    bybit_client_2 = None

logger = logging.getLogger(__name__)

async def switch_mirror_to_oneway_mode():
    """Switch mirror account to one-way mode using proper API"""
    
    print("🔄 Phase 2: Switch Mirror Account to One-Way Mode")
    
    if not MIRROR_AVAILABLE or not bybit_client_2:
        print("❌ Mirror trading not available")
        return False
    
    if not is_mirror_trading_enabled():
        print("❌ Mirror trading not enabled")
        return False
    
    try:
        # Step 1: Check current mode
        print("🔍 Checking current position mode...")
        
        account_info = bybit_client_2.get_account_info()
        if account_info and account_info.get('retCode') == 0:
            result = account_info.get('result', {})
            margin_mode = result.get('marginMode', 'UNKNOWN')
            print(f"   Current margin mode: {margin_mode}")
        
        # Step 2: Switch to One-Way Mode (mode=0)
        print("🔄 Switching to One-Way Mode (mode=0)...")
        
        # Use the proper v5 API endpoint
        result = bybit_client_2.switch_position_mode(
            category="linear",
            mode=0,  # 0 = One-Way Mode
            coin="USDT"  # Apply to all USDT contracts
        )
        
        if result and result.get('retCode') == 0:
            print("✅ Successfully switched mirror account to One-Way Mode")
            
            # Step 3: Verify the change
            print("🔍 Verifying position mode change...")
            await asyncio.sleep(2)  # Wait for change to take effect
            
            # Check by trying to get positions
            try:
                positions = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
                if positions and positions.get('retCode') == 0:
                    pos_list = positions.get('result', {}).get('list', [])
                    print(f"   Found {len(pos_list)} positions")
                    
                    # Check position structure for mode verification
                    for pos in pos_list[:3]:  # Check first 3 positions
                        symbol = pos.get('symbol', '')
                        pos_idx = pos.get('positionIdx', 'N/A')
                        print(f"     {symbol}: positionIdx={pos_idx}")
                        
                        # In one-way mode, positionIdx should be 0
                        if pos_idx != 0:
                            print(f"⚠️ Warning: {symbol} still has positionIdx={pos_idx}, may still be in hedge mode")
                else:
                    print("   No positions found or error getting positions")
                    
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

async def check_main_account_mode():
    """Check main account position mode for comparison"""
    try:
        print("🔍 Checking main account position mode...")
        
        account_info = bybit_client.get_account_info()
        if account_info and account_info.get('retCode') == 0:
            result = account_info.get('result', {})
            margin_mode = result.get('marginMode', 'UNKNOWN')
            print(f"   Main account margin mode: {margin_mode}")
            
            # Check main account positions
            try:
                positions = bybit_client.get_positions(category="linear", settleCoin="USDT")
                if positions and positions.get('retCode') == 0:
                    pos_list = positions.get('result', {}).get('list', [])
                    print(f"   Main account has {len(pos_list)} positions")
                    
                    # Check position structure
                    for pos in pos_list[:3]:
                        symbol = pos.get('symbol', '')
                        pos_idx = pos.get('positionIdx', 'N/A')
                        print(f"     {symbol}: positionIdx={pos_idx}")
                        
            except Exception as e:
                print(f"   Main account position check error: {e}")
            
            return margin_mode
        else:
            print("❌ Could not get main account info")
            return None
            
    except Exception as e:
        print(f"❌ Error checking main account: {e}")
        return None

if __name__ == "__main__":
    async def main():
        print("🚀 Starting Mirror Account Position Mode Switch")
        
        # Check main account mode first
        await check_main_account_mode()
        
        # Switch mirror account
        success = await switch_mirror_to_oneway_mode()
        
        if success:
            print("\n✅ Phase 2 completed successfully!")
            print("🎯 Mirror account is now in One-Way Mode")
            print("📋 Next: Update codebase to use One-Way Mode for mirror account")
        else:
            print("\n❌ Phase 2 failed!")
            print("⚠️ Manual intervention may be required")
    
    asyncio.run(main())