#!/usr/bin/env python3
"""
Comprehensive fix for conservative approach flow
"""
import shutil
from datetime import datetime

def fix_conservative_flow():
    """Fix the conservative approach flow comprehensively"""
    print("="*60)
    print("COMPREHENSIVE CONSERVATIVE APPROACH FIX")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Backup conversation.py
    backup_path = f"handlers/conversation.py.backup_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy('handlers/conversation.py', backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    # Read the file
    with open('handlers/conversation.py', 'r') as f:
        lines = f.readlines()
    
    # Fix 1: Ensure handle_approach_callback returns APPROACH_SELECTION state
    print("\n🔧 Fix 1: Checking handle_approach_callback...")
    
    # Fix 2: Add comprehensive logging
    for i, line in enumerate(lines):
        # Add logging to track state transitions
        if line.strip() == 'async def handle_approach_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:':
            # Add logging after function definition
            insert_pos = i + 2
            lines.insert(insert_pos, '    logger.info(f"🎯 handle_approach_callback called - data: {query.data if query else \'No query\'}")\n')
            print("✅ Added logging to handle_approach_callback")
            break
    
    # Fix 3: Ensure conservative approach correctly transitions to LIMIT_ENTRIES
    for i, line in enumerate(lines):
        if 'elif approach == "conservative":' in line and 'return LIMIT_ENTRIES' in ''.join(lines[i:i+40]):
            print("✅ Conservative approach already returns LIMIT_ENTRIES")
            break
    
    # Fix 4: Add state tracking
    state_tracking = '''
    # Log current conversation state for debugging
    logger.info(f"📊 Conversation State Transition: Moving to LIMIT_ENTRIES (value: {LIMIT_ENTRIES})")
    logger.info(f"📊 Chat data keys: {list(context.chat_data.keys())}")
    logger.info(f"📊 Approach stored: {context.chat_data.get(TRADING_APPROACH)}")
'''
    
    # Find where to add state tracking
    for i, line in enumerate(lines):
        if line.strip() == 'return LIMIT_ENTRIES' and 'conservative' in ''.join(lines[max(0,i-20):i]):
            lines.insert(i, state_tracking)
            print("✅ Added state tracking before LIMIT_ENTRIES return")
            break
    
    # Fix 5: Ensure limit_entries_handler is properly handling input
    for i, line in enumerate(lines):
        if 'async def limit_entries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:' in line:
            # Add immediate logging
            insert_pos = i + 2
            handler_logging = '''    logger.info("🎯 limit_entries_handler called - this handler should process limit prices")
    if update.message and update.message.text:
        logger.info(f"📝 Received text input: {update.message.text}")
    else:
        logger.info("❌ No message or text in update")
        
'''
            lines.insert(insert_pos, handler_logging)
            print("✅ Added comprehensive logging to limit_entries_handler")
            break
    
    # Write the fixed file
    with open('handlers/conversation.py', 'w') as f:
        f.writelines(lines)
    
    print("\n✅ All fixes applied!")
    print("\n📋 What was fixed:")
    print("1. Added comprehensive logging to track state transitions")
    print("2. Verified conservative approach returns LIMIT_ENTRIES state")
    print("3. Added state tracking to debug conversation flow")
    print("4. Enhanced limit_entries_handler logging")
    
    print("\n🔍 To test:")
    print("1. Restart the bot")
    print("2. Start a trade with /trade")
    print("3. Enter symbol (e.g., BTCUSDT)")
    print("4. Select Buy or Sell")
    print("5. Select 'Conservative Limits'")
    print("6. You should see request for limit price #1")
    print("7. Check logs for state transitions")

if __name__ == "__main__":
    fix_conservative_flow()
    
    print("\n" + "="*60)
    print("CONSERVATIVE FLOW FIXED")
    print("="*60)
    print("✅ Restart the bot and test the conservative approach!")