#!/usr/bin/env python3
"""
Phase 2: Complete Fast Approach Removal
=======================================

This script handles more comprehensive removal of fast approach references.
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def phase2_removal():
    """Phase 2 of fast approach removal"""
    
    # 1. Update mirror_trader.py
    logger.info("Updating mirror_trader.py...")
    try:
        with open('execution/mirror_trader.py', 'r') as f:
            content = f.read()
        
        # Force conservative approach
        content = re.sub(r'approach\s*=\s*["\']fast["\']', 'approach = "conservative"', content)
        content = re.sub(r'if\s+approach\s*==\s*["\']fast["\']:', 'if False:  # Fast approach removed', content)
        content = re.sub(r'approach\s*==\s*"fast"', 'False  # Fast approach removed', content)
        
        with open('execution/mirror_trader.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated mirror_trader.py")
    except Exception as e:
        logger.error(f"Error updating mirror_trader.py: {e}")
    
    # 2. Update mirror_enhanced_tp_sl.py
    logger.info("Updating mirror_enhanced_tp_sl.py...")
    try:
        with open('execution/mirror_enhanced_tp_sl.py', 'r') as f:
            content = f.read()
        
        content = re.sub(r'approach\s*==\s*["\']fast["\']', 'False  # Fast approach removed', content)
        content = re.sub(r'"approach":\s*approach', '"approach": "conservative"', content)
        
        with open('execution/mirror_enhanced_tp_sl.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated mirror_enhanced_tp_sl.py")
    except Exception as e:
        logger.error(f"Error updating mirror_enhanced_tp_sl.py: {e}")
    
    # 3. Update dashboard generator
    logger.info("Updating dashboard/generator_v2.py...")
    try:
        with open('dashboard/generator_v2.py', 'r') as f:
            content = f.read()
        
        # Remove fast approach emojis and text
        content = re.sub(r'approach_emoji\s*=\s*"🚀"\s*if\s*approach\s*==\s*"fast"\s*else\s*"🎯"', 
                        'approach_emoji = "🎯"  # Conservative only', content)
        content = re.sub(r'approach_text\s*=\s*"Fast"\s*if\s*approach\s*==\s*"fast"\s*else\s*"Conservative"',
                        'approach_text = "Conservative"', content)
        content = re.sub(r'if\s+approach\s*==\s*["\']fast["\']:', 'if False:  # Fast approach removed', content)
        
        with open('dashboard/generator_v2.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated dashboard/generator_v2.py")
    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
    
    # 4. Update constants
    logger.info("Updating config/constants.py...")
    try:
        with open('config/constants.py', 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if 'FAST_MARKET' in line or 'fast' in line.lower() and 'approach' in line.lower():
                new_lines.append(f"# {line.rstrip()} # Fast approach removed\n")
            else:
                new_lines.append(line)
        
        with open('config/constants.py', 'w') as f:
            f.writelines(new_lines)
        logger.info("✅ Updated constants.py")
    except Exception as e:
        logger.error(f"Error updating constants: {e}")
    
    # 5. Update conversation handlers more thoroughly
    logger.info("Further updating conversation.py...")
    try:
        with open('handlers/conversation.py', 'r') as f:
            content = f.read()
        
        # Remove approach selection function completely
        content = re.sub(
            r'async def show_approach_selection.*?(?=async def|\Z)', 
            '# Fast approach removed - function disabled\n', 
            content, 
            flags=re.DOTALL
        )
        
        # Remove approach handler
        content = re.sub(
            r'async def handle_approach_selection.*?(?=async def|\Z)',
            '# Fast approach removed - handler disabled\n',
            content,
            flags=re.DOTALL
        )
        
        # Update confirmation display
        content = re.sub(r'approach\s*=\s*context\.user_data\.get\("trading_approach",\s*"conservative"\)',
                        'approach = "conservative"  # Only conservative approach', content)
        
        with open('handlers/conversation.py', 'w') as f:
            f.write(content)
        logger.info("✅ Further updated conversation.py")
    except Exception as e:
        logger.error(f"Error further updating conversation.py: {e}")
    
    # 6. Update callbacks.py
    logger.info("Updating handlers/callbacks.py...")
    try:
        with open('handlers/callbacks.py', 'r') as f:
            content = f.read()
        
        # Remove fast approach callbacks
        content = re.sub(r'approach\s*==\s*["\']fast["\']', 'False  # Fast approach removed', content)
        content = re.sub(r'["\']approach["\']\s*:\s*["\']fast["\']', '"approach": "conservative"', content)
        
        with open('handlers/callbacks.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated callbacks.py")
    except Exception as e:
        logger.error(f"Error updating callbacks.py: {e}")
    
    # 7. Update trade messages
    logger.info("Updating execution/trade_messages.py...")
    try:
        with open('execution/trade_messages.py', 'r') as f:
            content = f.read()
        
        # Update approach displays
        content = re.sub(r'approach\s*==\s*["\']fast["\']', 'False', content)
        content = re.sub(r'Approach:\s*{approach}', 'Approach: Conservative', content)
        
        with open('execution/trade_messages.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated trade_messages.py")
    except Exception as e:
        logger.error(f"Error updating trade_messages.py: {e}")
    
    # 8. Clean up UI components
    logger.info("Updating dashboard components...")
    try:
        with open('dashboard/components.py', 'r') as f:
            content = f.read()
        
        content = re.sub(r'approach\s*==\s*["\']fast["\']', 'False', content)
        content = re.sub(r'"Fast Market"', '"Conservative"', content)
        
        with open('dashboard/components.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated components.py")
    except Exception as e:
        logger.error(f"Error updating components.py: {e}")
    
    # 9. Update any test files
    test_files = [
        'test_enhanced_dashboard.py',
        'test_alert_system.py',
        'test_button_handlers.py'
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            try:
                with open(test_file, 'r') as f:
                    content = f.read()
                
                content = re.sub(r'["\']fast["\']', '"conservative"', content)
                content = re.sub(r'["\']approach["\']\s*:\s*["\']fast["\']', '"approach": "conservative"', content)
                
                with open(test_file, 'w') as f:
                    f.write(content)
                logger.info(f"✅ Updated {test_file}")
            except Exception as e:
                logger.error(f"Error updating {test_file}: {e}")
    
    logger.info("\n✅ Phase 2 removal complete!")

if __name__ == "__main__":
    phase2_removal()