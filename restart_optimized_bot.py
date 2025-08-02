#!/usr/bin/env python3
"""
Emergency restart with performance optimization to resolve slowdown
"""
import os
import signal
import subprocess
import time

def restart_bot_optimized():
    """Restart bot with performance optimizations"""
    
    print("🚨 PERFORMANCE RESTART: Resolving bot slowdown")
    print("=" * 60)
    
    # 1. Kill existing bot instance
    print("1️⃣ Stopping existing bot...")
    try:
        # Get the bot process
        result = subprocess.run(['pgrep', '-f', 'python.*main.py'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            pid = result.stdout.strip()
            print(f"   Found bot process: PID {pid}")
            os.kill(int(pid), signal.SIGTERM)
            print("   ✅ Bot stopped gracefully")
            time.sleep(3)
        else:
            print("   ℹ️ No bot process found")
    except Exception as e:
        print(f"   ⚠️ Error stopping bot: {e}")
    
    # 2. Clear any stuck processes
    print("\n2️⃣ Cleaning up resources...")
    try:
        subprocess.run(['pkill', '-f', 'python.*main.py'], 
                      capture_output=True)
        print("   ✅ Process cleanup complete")
    except:
        pass
    
    # 3. Performance environment setup
    print("\n3️⃣ Setting performance environment...")
    performance_env = {
        # Enhanced HTTP Performance
        'HTTP_MAX_CONNECTIONS': '600',
        'HTTP_MAX_CONNECTIONS_PER_HOST': '150', 
        'HTTP_KEEPALIVE_TIMEOUT': '60',
        
        # Cache Performance
        'CACHE_DEFAULT_TTL': '300',
        'CACHE_MAX_SIZE': '1000',
        
        # Monitor Performance 
        'MAX_CONCURRENT_MONITORS': '20',  # Reduced from 50
        'POSITION_MONITOR_INTERVAL': '8',  # Increased from 5s to 8s
        
        # API Performance
        'API_RATE_LIMIT_CALLS_PER_SECOND': '4',  # Reduced from 5
        'API_RETRY_MAX_ATTEMPTS': '3',  # Reduced from 5
        
        # Memory Management
        'ENABLE_PERIODIC_GC': 'true',
        'GC_COLLECTION_INTERVAL': '300',  # 5 minutes
    }
    
    for key, value in performance_env.items():
        os.environ[key] = value
        print(f"   ✅ {key}={value}")
    
    # 4. Start optimized bot
    print("\n4️⃣ Starting optimized bot...")
    try:
        # Start bot in background with optimizations
        process = subprocess.Popen(
            ['python3', 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, **performance_env)
        )
        
        print(f"   🚀 Bot started with PID: {process.pid}")
        print("   ⚡ Performance optimizations active:")
        print("      • Reduced monitor interval: 8s (was 5s)")
        print("      • Limited concurrent monitors: 20 (was 50)")
        print("      • Optimized API rate limits")
        print("      • Enhanced memory management")
        
        # Wait a few seconds to check if it started successfully
        time.sleep(5)
        if process.poll() is None:
            print("   ✅ Bot is running successfully")
            
            # Show real-time startup logs for 10 seconds
            print("\n📋 Startup logs (10 seconds):")
            print("-" * 40)
            
            start_time = time.time()
            while time.time() - start_time < 10:
                if process.poll() is not None:
                    break
                try:
                    line = process.stdout.readline().decode('utf-8').strip()
                    if line:
                        print(f"   {line}")
                    time.sleep(0.1)
                except:
                    break
                    
        else:
            print("   ❌ Bot failed to start")
            return False
            
    except Exception as e:
        print(f"   ❌ Failed to start bot: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 RESTART COMPLETE!")
    print("💡 Monitor with: tail -f trading_bot.log")
    print("🔍 Check performance: grep 'Processed.*monitors' trading_bot.log")
    
    return True

if __name__ == "__main__":
    restart_bot_optimized()