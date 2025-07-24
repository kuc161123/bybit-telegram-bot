#!/usr/bin/env python3
"""
Safe shutdown script for the trading bot
Ensures all positions are monitored and data is saved before shutdown
"""
import os
import signal
import subprocess
import time
import pickle
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def find_bot_processes():
    """Find all running bot processes"""
    try:
        # Find all python processes running main.py
        result = subprocess.run(
            ["ps", "aux"], 
            capture_output=True, 
            text=True
        )
        
        processes = []
        for line in result.stdout.split('\n'):
            if 'python' in line and 'main.py' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    processes.append((pid, line.strip()))
        
        return processes
    except Exception as e:
        logger.error(f"Error finding processes: {e}")
        return []

def save_current_state():
    """Save current bot state before shutdown"""
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_shutdown_{int(time.time())}'
        
        # Create backup
        if os.path.exists(pkl_path):
            subprocess.run(['cp', pkl_path, backup_path])
            logger.info(f"✅ Created backup: {backup_path}")
            
            # Check monitor count
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            logger.info(f"📊 Current monitors: {len(monitors)}")
            
    except Exception as e:
        logger.error(f"Error saving state: {e}")

def kill_bot_safely():
    """Safely shutdown all bot instances"""
    logger.info("🛑 Starting safe shutdown process...")
    
    # Find all bot processes
    processes = find_bot_processes()
    
    if not processes:
        logger.info("✅ No bot instances found running")
        return
    
    logger.info(f"Found {len(processes)} bot instance(s):")
    for pid, info in processes:
        logger.info(f"  PID {pid}: {info[:100]}...")
    
    # Save current state
    save_current_state()
    
    # Send SIGTERM for graceful shutdown
    logger.info("📤 Sending graceful shutdown signal (SIGTERM)...")
    for pid, _ in processes:
        try:
            os.kill(int(pid), signal.SIGTERM)
            logger.info(f"  Sent SIGTERM to PID {pid}")
        except Exception as e:
            logger.error(f"  Error sending SIGTERM to {pid}: {e}")
    
    # Wait for graceful shutdown
    logger.info("⏳ Waiting 5 seconds for graceful shutdown...")
    time.sleep(5)
    
    # Check if processes still running
    remaining = find_bot_processes()
    
    if remaining:
        logger.warning(f"⚠️ {len(remaining)} process(es) still running, sending SIGKILL...")
        for pid, _ in remaining:
            try:
                os.kill(int(pid), signal.SIGKILL)
                logger.info(f"  Sent SIGKILL to PID {pid}")
            except Exception as e:
                logger.error(f"  Error sending SIGKILL to {pid}: {e}")
        
        time.sleep(2)
    
    # Final check
    final_check = find_bot_processes()
    if final_check:
        logger.error("❌ Some processes may still be running:")
        for pid, info in final_check:
            logger.error(f"  PID {pid}: {info[:100]}...")
    else:
        logger.info("✅ All bot instances successfully stopped")
    
    # Clean up any lock files
    lock_files = [
        'bot.lock',
        '.bot_running',
        'reload_enhanced_monitors.signal',
        '.force_load_all_monitors'
    ]
    
    for lock_file in lock_files:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            logger.info(f"🧹 Removed lock file: {lock_file}")

if __name__ == "__main__":
    kill_bot_safely()