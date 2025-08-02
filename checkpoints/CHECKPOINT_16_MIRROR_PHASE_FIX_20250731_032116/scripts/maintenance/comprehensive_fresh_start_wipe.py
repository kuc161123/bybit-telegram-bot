#!/usr/bin/env python3
"""
Comprehensive wipe of ALL bot data and kill all instances
This gives a complete fresh start
"""

import os
import shutil
import logging
import subprocess
import signal
import time
from datetime import datetime
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def kill_all_bot_processes():
    """Kill all bot processes including hidden ones"""
    logger.info("\n🔪 KILLING ALL BOT PROCESSES")
    logger.info("="*60)
    
    # Patterns to search for
    process_patterns = [
        "python.*main.py",
        "python3.*main.py",
        "python.*bybit.*bot",
        "python.*trading.*bot",
        "telegram.*bot.*bybit"
    ]
    
    killed_count = 0
    
    # Method 1: Using pkill
    for pattern in process_patterns:
        try:
            result = subprocess.run(['pkill', '-f', pattern], capture_output=True, text=True)
            if result.returncode == 0:
                killed_count += 1
                logger.info(f"✅ Killed processes matching: {pattern}")
        except Exception as e:
            logger.debug(f"pkill failed for {pattern}: {e}")
    
    # Method 2: Using ps and kill
    try:
        # Get all python processes
        ps_output = subprocess.run(['ps', 'aux'], capture_output=True, text=True).stdout
        
        for line in ps_output.split('\n'):
            if 'python' in line and ('main.py' in line or 'bybit' in line or 'trading_bot' in line):
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        killed_count += 1
                        logger.info(f"✅ Killed PID {pid}: {' '.join(parts[10:])[:50]}...")
                        time.sleep(0.1)
                        # Force kill if still running
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except:
                            pass
                    except Exception as e:
                        logger.debug(f"Failed to kill PID {pid}: {e}")
    except Exception as e:
        logger.error(f"Error scanning processes: {e}")
    
    # Method 3: Kill screen/tmux sessions
    try:
        # Kill screen sessions
        subprocess.run(['screen', '-ls'], capture_output=True)
        subprocess.run(['pkill', '-f', 'SCREEN.*bybit'], capture_output=True)
        
        # Kill tmux sessions with bot
        result = subprocess.run(['tmux', 'list-sessions'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'bot' in line.lower() or 'bybit' in line.lower():
                    session_name = line.split(':')[0]
                    subprocess.run(['tmux', 'kill-session', '-t', session_name])
                    logger.info(f"✅ Killed tmux session: {session_name}")
    except:
        pass
    
    logger.info(f"\n✅ Killed {killed_count} bot processes")

def wipe_bot_data():
    """Wipe all bot data files"""
    logger.info("\n🗑️ WIPING ALL BOT DATA")
    logger.info("="*60)
    
    # Files and patterns to delete
    files_to_delete = [
        # Main data files
        'bybit_bot_dashboard_v4.1_enhanced.pkl',
        'alerts_data.pkl',
        'bot_restart_log.txt',
        'trading_bot.log*',
        'fresh_start_completed.txt',
        '.fresh_start_marker',
        
        # Backup files
        '*.pkl.backup*',
        '*.bak',
        
        # Cache files
        'cache/*.json',
        '__pycache__',
        '.persistence_checksum',
        
        # Temporary files
        '*.tmp',
        '*.temp',
        
        # Old monitors and state files
        '*monitor*.pkl',
        '*position*.pkl',
        '*state*.pkl',
        
        # Log files
        '*.log',
        '*.log.*',
        'logs/*',
        
        # Lock files
        '*.lock',
        '.*.lock',
        
        # Session files
        '.telegram*',
        'session*',
        
        # Debug files
        'debug_*.png',
        'debug_*.txt',
        'debug_*.json',
    ]
    
    deleted_count = 0
    
    for pattern in files_to_delete:
        # Handle wildcards
        if '*' in pattern:
            files = glob.glob(pattern)
            for file in files:
                try:
                    if os.path.isfile(file):
                        os.remove(file)
                        deleted_count += 1
                        logger.info(f"✅ Deleted: {file}")
                    elif os.path.isdir(file):
                        shutil.rmtree(file)
                        deleted_count += 1
                        logger.info(f"✅ Deleted directory: {file}")
                except Exception as e:
                    logger.debug(f"Failed to delete {file}: {e}")
        else:
            # Single file
            try:
                if os.path.exists(pattern):
                    if os.path.isfile(pattern):
                        os.remove(pattern)
                    else:
                        shutil.rmtree(pattern)
                    deleted_count += 1
                    logger.info(f"✅ Deleted: {pattern}")
            except Exception as e:
                logger.debug(f"Failed to delete {pattern}: {e}")
    
    # Clean Python cache
    try:
        subprocess.run(['find', '.', '-type', 'd', '-name', '__pycache__', '-exec', 'rm', '-rf', '{}', '+'], 
                      capture_output=True)
        logger.info("✅ Cleaned Python cache")
    except:
        pass
    
    logger.info(f"\n✅ Deleted {deleted_count} files/directories")

def create_fresh_environment():
    """Create fresh environment markers"""
    logger.info("\n🌱 CREATING FRESH ENVIRONMENT")
    logger.info("="*60)
    
    # Create fresh start marker
    with open('.fresh_start', 'w') as f:
        f.write(f"Fresh start initiated: {datetime.now()}\n")
        f.write("All data wiped and processes killed\n")
    
    # Create empty required directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('cache', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    logger.info("✅ Created fresh environment markers")

def main():
    """Main execution"""
    logger.info("🚨 COMPREHENSIVE FRESH START WIPE")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # Warning
    logger.warning("\n⚠️  WARNING: This will:")
    logger.warning("   1. Kill ALL bot processes")
    logger.warning("   2. Delete ALL bot data")
    logger.warning("   3. Remove ALL history and logs")
    logger.warning("\n   This action is IRREVERSIBLE!")
    
    logger.info("\nStarting in 5 seconds... Press Ctrl+C to cancel")
    
    try:
        for i in range(5, 0, -1):
            logger.info(f"   {i}...")
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n❌ Cancelled by user")
        return
    
    # Step 1: Kill all processes
    kill_all_bot_processes()
    
    # Wait for processes to die
    logger.info("\n⏳ Waiting for processes to terminate...")
    time.sleep(3)
    
    # Step 2: Wipe all data
    wipe_bot_data()
    
    # Step 3: Create fresh environment
    create_fresh_environment()
    
    # Final verification
    logger.info("\n🔍 VERIFICATION")
    logger.info("="*60)
    
    # Check for remaining processes
    remaining = subprocess.run(['pgrep', '-f', 'python.*main.py'], 
                             capture_output=True).returncode == 0
    
    if remaining:
        logger.warning("⚠️ Some processes may still be running")
        logger.info("   Run: kill -9 $(pgrep -f 'python.*main.py')")
    else:
        logger.info("✅ No bot processes found")
    
    # Check for data files
    if os.path.exists('bybit_bot_dashboard_v4.1_enhanced.pkl'):
        logger.warning("⚠️ Main data file still exists")
    else:
        logger.info("✅ Main data file removed")
    
    logger.info("\n" + "="*60)
    logger.info("✅ COMPREHENSIVE FRESH START COMPLETE")
    logger.info("="*60)
    logger.info("\n🚀 You now have a completely fresh environment!")
    logger.info("   - All processes killed")
    logger.info("   - All data wiped")
    logger.info("   - Ready for fresh bot deployment")
    
    logger.info("\n💡 Next steps:")
    logger.info("   1. Review your .env configuration")
    logger.info("   2. Start the bot fresh: python main.py")
    logger.info("   3. Use Conservative approach for all new positions")

if __name__ == "__main__":
    main()