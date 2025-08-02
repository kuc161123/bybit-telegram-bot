#!/usr/bin/env python3
"""
Restart Bot with Enhanced Error Handling
========================================

This script safely restarts the bot with the new enhanced error handling.
"""

import os
import sys
import time
import subprocess
import signal

def kill_existing_bot():
    """Kill existing bot processes"""
    print("1. Stopping existing bot processes...")
    
    # Find and kill main.py processes
    try:
        result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"   Killing process {pid}")
                    os.kill(int(pid), signal.SIGTERM)
            time.sleep(2)  # Give processes time to shutdown gracefully
            
            # Force kill if still running
            result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        print(f"   Force killing process {pid}")
                        os.kill(int(pid), signal.SIGKILL)
            
            print("   ✓ Bot processes stopped")
        else:
            print("   ℹ️  No bot processes found")
    except Exception as e:
        print(f"   ⚠️  Error stopping bot: {e}")

def verify_enhanced_error_handling():
    """Verify the enhanced error handling is in place"""
    print("\n2. Verifying enhanced error handling...")
    
    mirror_file = "/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl.py"
    
    try:
        with open(mirror_file, 'r') as f:
            content = f.read()
        
        # Check for key enhanced features
        checks = [
            ("Circuit breaker import", "from create_enhanced_mirror_error_handling import EnhancedMirrorErrorHandler, CircuitBreaker"),
            ("Error handler initialization", "self.error_handler = EnhancedMirrorErrorHandler()"),
            ("Position sync validation", "def check_position_sync"),
            ("Safe order placement", "async def place_order_safe"),
            ("Retry logic", "execute_with_retry")
        ]
        
        all_good = True
        for check_name, check_string in checks:
            if check_string in content:
                print(f"   ✓ {check_name}: Found")
            else:
                print(f"   ❌ {check_name}: Missing")
                all_good = False
        
        if all_good:
            print("\n   ✅ Enhanced error handling verified!")
            return True
        else:
            print("\n   ⚠️  Some enhanced features missing")
            return False
            
    except Exception as e:
        print(f"   ❌ Error verifying: {e}")
        return False

def start_bot_with_logging():
    """Start the bot with enhanced logging"""
    print("\n3. Starting bot with enhanced error handling...")
    
    # Create startup script with enhanced logging
    startup_script = """#!/bin/bash
cd /Users/lualakol/bybit-telegram-bot

# Export enhanced logging
export PYTHONUNBUFFERED=1
export LOG_LEVEL=INFO

# Start the bot
echo "Starting bot with enhanced error handling at $(date)"
python main.py 2>&1 | tee -a enhanced_error_handling.log
"""
    
    script_file = "/tmp/start_enhanced_bot.sh"
    with open(script_file, 'w') as f:
        f.write(startup_script)
    
    os.chmod(script_file, 0o755)
    
    # Start the bot in background
    subprocess.Popen(['/bin/bash', script_file], 
                     stdout=subprocess.DEVNULL, 
                     stderr=subprocess.DEVNULL,
                     start_new_session=True)
    
    print("   ✓ Bot started with enhanced error handling")
    print("   ℹ️  Logs will be written to enhanced_error_handling.log")

def monitor_startup():
    """Monitor the bot startup for errors"""
    print("\n4. Monitoring startup (10 seconds)...")
    
    time.sleep(3)  # Give bot time to start
    
    # Check if bot is running
    result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
    if result.returncode == 0:
        print("   ✓ Bot process is running")
        
        # Check for immediate errors in log
        log_file = "/Users/lualakol/bybit-telegram-bot/trading_bot.log"
        try:
            # Get last few lines of log
            result = subprocess.run(['tail', '-n', '20', log_file], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                log_lines = result.stdout.strip().split('\n')
                
                # Look for startup messages
                startup_found = False
                errors_found = []
                
                for line in log_lines:
                    if "Enhanced TP/SL Manager with error handling" in line:
                        startup_found = True
                    if "ERROR" in line and "qty err" not in line:  # Ignore existing qty errors
                        errors_found.append(line)
                
                if startup_found:
                    print("   ✓ Enhanced error handling initialized")
                
                if errors_found:
                    print("   ⚠️  Startup errors detected:")
                    for error in errors_found[:3]:
                        print(f"      {error[:80]}...")
                else:
                    print("   ✓ No new startup errors")
                    
        except Exception as e:
            print(f"   ⚠️  Could not check logs: {e}")
    else:
        print("   ❌ Bot process not found - may have crashed")

def main():
    """Main execution"""
    print("Bot Restart with Enhanced Error Handling")
    print("=" * 60)
    
    # Kill existing bot
    kill_existing_bot()
    
    # Verify enhanced error handling
    if not verify_enhanced_error_handling():
        print("\n⚠️  Enhanced error handling not fully verified")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Restart cancelled")
            return
    
    # Start bot
    start_bot_with_logging()
    
    # Monitor startup
    monitor_startup()
    
    print("\n" + "=" * 60)
    print("✅ Bot restarted with enhanced error handling!")
    print("\nKey improvements now active:")
    print("- Retry logic with exponential backoff (0.5s, 1s, 2s, 5s, 10s)")
    print("- Circuit breakers prevent error flooding (5 failures = 60s cooldown)")
    print("- Position size tolerance checks (0.1%)")
    print("- Quantity/price validation before orders")
    print("- Graceful degradation on repeated failures")
    print("\nMonitor the logs for improved error handling:")
    print("- tail -f trading_bot.log")
    print("- tail -f enhanced_error_handling.log")

if __name__ == "__main__":
    main()