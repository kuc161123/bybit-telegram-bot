#!/usr/bin/env python3
"""
Script to clear all caches and force the new enhanced UI to display
Run this to ensure the new dashboard v5.0 is shown
"""

import os
import glob

def clear_cache():
    """Clear all cache files and force UI refresh"""
    
    print("🧹 Clearing all cache files...")
    
    # Clear any pickle files that might cache dashboard state
    pickle_files = glob.glob("*.pkl") + glob.glob("*.pickle")
    for pf in pickle_files:
        if "dashboard" in pf.lower():
            try:
                os.remove(pf)
                print(f"✅ Removed {pf}")
            except Exception as e:
                print(f"⚠️ Could not remove {pf}: {e}")
    
    # Clear Python cache
    pycache_dirs = glob.glob("**/__pycache__", recursive=True)
    for cache_dir in pycache_dirs:
        try:
            import shutil
            shutil.rmtree(cache_dir)
            print(f"✅ Cleared {cache_dir}")
        except Exception as e:
            print(f"⚠️ Could not clear {cache_dir}: {e}")
    
    print("\n✨ Cache clearing complete!")
    print("\n📱 To see the new enhanced UI:")
    print("1. Restart the bot: python main.py")
    print("2. Use /dashboard or /start command")
    print("3. The new v5.0 dashboard with visual enhancements will appear!")
    print("\n🎨 New features include:")
    print("- Visual progress bars for margin usage")
    print("- Enhanced P&L matrix with quality ratings")
    print("- Beautiful position cards with visual indicators")
    print("- Market pulse section with live indicators")
    print("- Quick actions bar with grid layout")
    print("- Professional footer with countdown timer")

if __name__ == "__main__":
    clear_cache()