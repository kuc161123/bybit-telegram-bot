#!/usr/bin/env python3
"""
Sync monitor position sizes with actual values from Bybit exchanges.
Updates stored position_size in Enhanced TP/SL monitors to match actual positions.
"""

import asyncio
import pickle
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from tabulate import tabulate
from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET

class MonitorPositionSync:
    def __init__(self):
        self.bybit_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        self.mirror_client = None
        if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            self.mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
        
        self.pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    def create_backup(self) -> str:
        """Create a backup of the pickle file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.pickle_file}.backup_sync_{timestamp}"
        
        try:
            import shutil
            shutil.copy2(self.pickle_file, backup_file)
            print(f"✅ Created backup: {backup_file}")
            return backup_file
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
            raise
    
    def load_pickle_data(self) -> Dict[str, Any]:
        """Load data from pickle file."""
        if not os.path.exists(self.pickle_file):
            print(f"❌ Pickle file not found: {self.pickle_file}")
            return {}
        
        try:
            with open(self.pickle_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"❌ Error loading pickle file: {e}")
            return {}
    
    def save_pickle_data(self, data: Dict[str, Any]):
        """Save data to pickle file."""
        try:
            with open(self.pickle_file, 'wb') as f:
                pickle.dump(data, f)
            print(f"✅ Saved updated data to {self.pickle_file}")
        except Exception as e:
            print(f"❌ Error saving pickle file: {e}")
            raise
    
    def get_positions(self, client: HTTP) -> Dict[str, Dict[str, Any]]:
        """Get all positions from Bybit."""
        positions = {}
        try:
            response = client.get_positions(category="linear", settleCoin="USDT")
            if response["retCode"] == 0:
                for pos in response["result"]["list"]:
                    if float(pos["size"]) > 0:
                        symbol = pos["symbol"]
                        side = pos["side"]
                        key = f"{symbol}_{side}"
                        positions[key] = {
                            "symbol": symbol,
                            "side": side,
                            "size": float(pos["size"]),
                            "avgPrice": float(pos["avgPrice"]),
                            "markPrice": float(pos["markPrice"]),
                            "unrealisedPnl": float(pos["unrealisedPnl"])
                        }
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
        
        return positions
    
    def sync_monitors(self):
        """Sync monitor position sizes with actual exchange values."""
        print("=" * 80)
        print("MONITOR POSITION SYNC")
        print("=" * 80)
        print()
        
        # Create backup first
        backup_file = self.create_backup()
        print()
        
        # Load pickle data
        data = self.load_pickle_data()
        if not data:
            return
        
        # Get actual positions from both exchanges
        print("📊 Fetching positions from exchanges...")
        main_positions = self.get_positions(self.bybit_client)
        mirror_positions = self.get_positions(self.mirror_client) if self.mirror_client else {}
        
        print(f"  Main account: {len(main_positions)} positions")
        print(f"  Mirror account: {len(mirror_positions)} positions")
        print()
        
        # Get Enhanced TP/SL monitors
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📋 Processing {len(enhanced_monitors)} Enhanced TP/SL monitors...")
        print()
        
        # Track updates
        updates = []
        errors = []
        
        for monitor_key, monitor_info in enhanced_monitors.items():
            symbol = monitor_info.get('symbol', 'Unknown')
            side = monitor_info.get('side', 'Unknown')
            account_type = monitor_info.get('account_type', 'main')
            old_size = float(monitor_info.get('position_size', 0))
            
            # Get actual position
            actual_positions = main_positions if account_type == 'main' else mirror_positions
            position_key = f"{symbol}_{side}"
            actual_pos = actual_positions.get(position_key)
            
            if actual_pos:
                new_size = actual_pos['size']
                
                # Update monitor with new size (keep as Decimal for consistency)
                monitor_info['position_size'] = Decimal(str(new_size))
                
                # Track update
                updates.append({
                    "Symbol": symbol,
                    "Side": side,
                    "Account": account_type,
                    "Old Size": f"{old_size:.4f}",
                    "New Size": f"{new_size:.4f}",
                    "Change": f"{new_size - old_size:.4f}"
                })
            else:
                # No position found
                errors.append({
                    "Symbol": symbol,
                    "Side": side,
                    "Account": account_type,
                    "Issue": "No position found on exchange"
                })
        
        # Display updates
        if updates:
            print("✅ SUCCESSFUL UPDATES:")
            print(tabulate(updates, headers="keys", tablefmt="grid"))
            print()
        
        # Display errors
        if errors:
            print("⚠️  ERRORS (monitors without positions):")
            print(tabulate(errors, headers="keys", tablefmt="grid"))
            print()
        
        # Save updated data
        if updates:
            print(f"💾 Saving {len(updates)} updates to pickle file...")
            self.save_pickle_data(data)
            print()
        else:
            print("ℹ️  No updates needed - all monitors already have correct sizes")
            print()
        
        # Summary
        print("=" * 80)
        print("SYNC SUMMARY")
        print("=" * 80)
        print(f"✓ Total monitors processed: {len(enhanced_monitors)}")
        print(f"✓ Successful updates: {len(updates)}")
        print(f"✓ Errors: {len(errors)}")
        print(f"✓ Backup created: {backup_file}")
        
        if updates:
            print(f"\n✅ Monitor position sizes have been synchronized with exchange values!")
            print("\n📌 IMPORTANT: No restart required!")
            print("   The Enhanced TP/SL monitoring system will use the updated values immediately")
            print("   on the next monitoring cycle (within 5 seconds).")
        
        # Verify sync by re-checking
        if updates:
            print("\n🔍 Verifying sync...")
            self.verify_sync()
    
    def verify_sync(self):
        """Verify that monitor sizes now match exchange positions."""
        # Reload data
        data = self.load_pickle_data()
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Get fresh positions
        main_positions = self.get_positions(self.bybit_client)
        mirror_positions = self.get_positions(self.mirror_client) if self.mirror_client else {}
        
        # Check for mismatches
        mismatches = 0
        for monitor_key, monitor_info in enhanced_monitors.items():
            symbol = monitor_info.get('symbol')
            side = monitor_info.get('side')
            account_type = monitor_info.get('account_type', 'main')
            monitor_size = float(monitor_info.get('position_size', 0))
            
            actual_positions = main_positions if account_type == 'main' else mirror_positions
            position_key = f"{symbol}_{side}"
            actual_pos = actual_positions.get(position_key)
            
            if actual_pos:
                actual_size = actual_pos['size']
                if abs(monitor_size - actual_size) > 0.0001:
                    print(f"  ❌ Mismatch: {symbol} {side} ({account_type}) - Monitor: {monitor_size}, Actual: {actual_size}")
                    mismatches += 1
        
        if mismatches == 0:
            print("  ✅ All monitor sizes match exchange positions!")
        else:
            print(f"  ⚠️  Found {mismatches} mismatches after sync")

async def main():
    """Main function."""
    syncer = MonitorPositionSync()
    syncer.sync_monitors()

if __name__ == "__main__":
    asyncio.run(main())