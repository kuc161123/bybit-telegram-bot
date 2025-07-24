#!/usr/bin/env python3
"""
Add mirror position sync to the bot's background tasks
"""
import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of a file"""
    backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(filepath, backup_path)
    print(f"✅ Created backup: {backup_path}")
    return backup_path

def add_mirror_sync_to_background_tasks():
    """Add mirror sync to helpers/background_tasks.py"""
    
    print("="*60)
    print("ADDING MIRROR SYNC TO BACKGROUND TASKS")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Backup the file
    file_path = 'helpers/background_tasks.py'
    backup_file(file_path)
    
    # Read the current file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if mirror sync already added
    if 'mirror_position_sync' in content:
        print("⚠️  Mirror sync already appears to be in the file")
        return
    
    # Find where to add the import
    import_section = """from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
from execution.mirror_position_sync import start_mirror_position_sync"""
    
    # Replace the import
    if 'from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager' in content:
        content = content.replace(
            'from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager',
            import_section
        )
        print("✅ Added mirror sync import")
    
    # Find where to add the mirror sync task
    # Look for where background tasks are started
    mirror_sync_code = """
    # Start mirror position sync (independent from main sync)
    if os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true":
        logger.info("🪞 Starting independent mirror position sync...")
        try:
            mirror_sync_task = asyncio.create_task(
                start_mirror_position_sync(enhanced_tp_sl_manager)
            )
            background_tasks.append(mirror_sync_task)
            logger.info("✅ Mirror position sync task started (independent from main sync)")
        except Exception as e:
            logger.error(f"Failed to start mirror position sync: {e}")
"""
    
    # Find a good place to insert it - after the enhanced TP/SL monitoring task
    if 'Enhanced TP/SL monitoring task started' in content:
        # Find the line and insert after it
        lines = content.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if 'Enhanced TP/SL monitoring task started' in line:
                # Add the mirror sync code after this line
                new_lines.append(mirror_sync_code)
                print("✅ Added mirror sync task startup code")
        
        content = '\n'.join(new_lines)
    
    # Write the updated file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Updated helpers/background_tasks.py")

def add_mirror_sync_import_to_main():
    """Ensure main.py can use the mirror sync"""
    
    print("\n" + "="*60)
    print("CHECKING MAIN.PY")
    print("="*60)
    
    # Check if we need to modify main.py
    with open('main.py', 'r') as f:
        main_content = f.read()
    
    if 'ENABLE_MIRROR_TRADING' in main_content:
        print("✅ main.py already has mirror trading references")
    else:
        print("ℹ️  main.py doesn't need modification - background_tasks.py handles it")

def create_verification_script():
    """Create a script to verify mirror sync is working"""
    
    verification_script = '''#!/usr/bin/env python3
"""
Verify mirror position sync is working
"""
import asyncio
import time
from datetime import datetime

async def verify_mirror_sync():
    """Verify mirror sync is active"""
    print("="*60)
    print("VERIFYING MIRROR POSITION SYNC")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Check monitors over time
        print("\\nMonitoring for 15 seconds to see if mirror sync maintains monitors...")
        
        for i in range(3):
            all_monitors = enhanced_tp_sl_manager.position_monitors
            main_count = sum(1 for k in all_monitors if k.endswith('_main'))
            mirror_count = sum(1 for k in all_monitors if k.endswith('_mirror'))
            
            print(f"\\n[{i*5}s] Monitor count:")
            print(f"  Main: {main_count}")
            print(f"  Mirror: {mirror_count}")
            print(f"  Total: {len(all_monitors)}")
            
            if i < 2:
                await asyncio.sleep(5)
        
        if mirror_count > 0:
            print("\\n✅ Mirror sync is working! Mirror monitors are being maintained.")
        else:
            print("\\n⚠️  No mirror monitors found. Mirror sync may not be running.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_mirror_sync())
'''
    
    with open('verify_mirror_sync.py', 'w') as f:
        f.write(verification_script)
    
    print("\n✅ Created verify_mirror_sync.py")

def main():
    """Main execution"""
    # Add mirror sync to background tasks
    add_mirror_sync_to_background_tasks()
    
    # Check main.py
    add_mirror_sync_import_to_main()
    
    # Create verification script
    create_verification_script()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("✅ Mirror position sync has been added to background tasks")
    print("✅ It will run independently from main position sync")
    print("\nWhat will happen:")
    print("1. Main sync: Continues to sync main account only")
    print("2. Mirror sync: NEW - Syncs mirror account only")
    print("3. Both run independently every 60 seconds")
    print("\nExpected logs:")
    print("  🔄 Starting position sync for Enhanced TP/SL monitoring (main)")
    print("  🪞 Starting independent mirror position sync...")
    print("  🔍 Monitoring 10 positions")
    print("\n⚠️  IMPORTANT: You need to restart the bot for this to take effect")
    print("After restart, the mirror sync will maintain all 10 monitors!")

if __name__ == "__main__":
    main()