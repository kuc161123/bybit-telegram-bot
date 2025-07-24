#!/usr/bin/env python3
"""
Complete Removal of Fast Approach Feature
=========================================

This script removes all traces of the fast approach trading feature,
leaving only the conservative approach.
"""

import os
import re
import logging
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FastApproachRemover:
    def __init__(self):
        self.files_to_modify = []
        self.backup_dir = "backup_before_fast_removal"
        
    def find_files_with_fast_approach(self) -> List[str]:
        """Find all files that mention fast approach"""
        files_with_fast = []
        
        # Directories to search
        search_dirs = [
            'execution',
            'handlers', 
            'dashboard',
            'config',
            'utils',
            'clients'
        ]
        
        # Also check root level Python files
        for file in os.listdir('.'):
            if file.endswith('.py'):
                search_dirs.append(file)
        
        for dir_or_file in search_dirs:
            if os.path.isfile(dir_or_file):
                try:
                    with open(dir_or_file, 'r') as f:
                        content = f.read()
                        if any(term in content.lower() for term in ['fast', 'approach_selection', 'trading_approach']):
                            files_with_fast.append(dir_or_file)
                except:
                    pass
            elif os.path.isdir(dir_or_file):
                for root, dirs, files in os.walk(dir_or_file):
                    for file in files:
                        if file.endswith('.py'):
                            filepath = os.path.join(root, file)
                            try:
                                with open(filepath, 'r') as f:
                                    content = f.read()
                                    if any(term in content.lower() for term in ['fast', 'approach_selection', 'trading_approach']):
                                        files_with_fast.append(filepath)
                            except:
                                pass
        
        return files_with_fast
    
    def create_backup(self, files: List[str]):
        """Create backups of files before modification"""
        import shutil
        
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        for file in files:
            backup_path = os.path.join(self.backup_dir, file.replace('/', '_'))
            try:
                shutil.copy2(file, backup_path)
                logger.info(f"Backed up: {file}")
            except Exception as e:
                logger.error(f"Failed to backup {file}: {e}")
    
    def get_modifications(self) -> List[Tuple[str, List[Tuple[str, str]]]]:
        """Get all modifications to be made"""
        modifications = []
        
        # 1. handlers/conversation.py - Remove approach selection
        modifications.append(('handlers/conversation.py', [
            # Remove approach selection state
            ('APPROACH_SELECTION, ', ''),
            ('APPROACH_SELECTION = range', 'MARGIN = range'),
            # Remove approach keyboard
            ('await show_approach_selection', '# Approach selection removed - using conservative only\n    context.user_data["trading_approach"] = "conservative"\n    await show_margin_input'),
            # Remove approach selection handler
            ('async def handle_approach_selection', '# Fast approach removed - function disabled\nasync def handle_approach_selection'),
            # Update confirmation to not show approach
            ('"Approach": approach.title()', '"Approach": "Conservative"'),
            # Skip approach selection in flow
            ('return APPROACH_SELECTION', 'context.user_data["trading_approach"] = "conservative"\n    return MARGIN'),
        ]))
        
        # 2. execution/trader.py - Remove fast execution logic
        modifications.append(('execution/trader.py', [
            # Import only conservative merger
            ('from execution.position_merger import ConservativePositionMerger, FastPositionMerger', 
             'from execution.position_merger import ConservativePositionMerger'),
            # Remove fast merger initialization
            ('self.fast_position_merger = FastPositionMerger()', '# Fast merger removed'),
            # Force conservative approach
            ('approach = execution_params.get("approach", "conservative")',
             'approach = "conservative"  # Fast approach removed, only conservative'),
            # Remove fast approach condition
            ('if approach == "fast":', 'if False:  # Fast approach removed'),
            # Clean up approach checks
            ('approach.lower() == "fast"', 'False  # Fast approach removed'),
        ]))
        
        # 3. execution/position_merger.py - Remove FastPositionMerger class
        modifications.append(('execution/position_merger.py', [
            ('class FastPositionMerger:', '# Fast approach removed\n# class FastPositionMerger:'),
            # Comment out entire class - this needs special handling
        ]))
        
        # 4. execution/enhanced_tp_sl_manager.py - Remove fast approach logic
        modifications.append(('execution/enhanced_tp_sl_manager.py', [
            # Remove fast approach checks
            ('monitor_data.get("approach") == "fast"', 'False  # Fast approach removed'),
            ('approach == "fast"', 'False  # Fast approach removed'),
            # Default to conservative
            ('"approach": approach', '"approach": "conservative"'),
        ]))
        
        # 5. dashboard/generator_v2.py - Remove fast approach from UI
        modifications.append(('dashboard/generator_v2.py', [
            # Remove fast approach display
            ('approach_emoji = "🚀" if approach == "fast" else "🎯"', 
             'approach_emoji = "🎯"  # Conservative only'),
            ('approach_text = "Fast" if approach == "fast" else "Conservative"',
             'approach_text = "Conservative"'),
            # Remove approach from stats
            ('"fast_trades":', '"fast_trades": 0,  # Fast approach removed'),
        ]))
        
        # 6. config/constants.py - Remove fast approach constants
        modifications.append(('config/constants.py', [
            # Remove fast approach options
            ('FAST_MARKET = "fast"', '# FAST_MARKET = "fast"  # Removed'),
            ('CONSERVATIVE_LIMITS = "conservative"', 'CONSERVATIVE_LIMITS = "conservative"  # Only approach'),
        ]))
        
        # 7. Remove fast approach from mirror trading
        modifications.append(('execution/mirror_trader.py', [
            ('approach == "fast"', 'False  # Fast approach removed'),
            ('"approach": approach', '"approach": "conservative"'),
        ]))
        
        return modifications
    
    def apply_modifications(self, modifications: List[Tuple[str, List[Tuple[str, str]]]]):
        """Apply all modifications to remove fast approach"""
        for filepath, changes in modifications:
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                continue
                
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                original_content = content
                
                for old_text, new_text in changes:
                    if old_text in content:
                        content = content.replace(old_text, new_text)
                        logger.info(f"Modified in {filepath}: {old_text[:50]}...")
                
                if content != original_content:
                    with open(filepath, 'w') as f:
                        f.write(content)
                    logger.info(f"✅ Updated: {filepath}")
                    
            except Exception as e:
                logger.error(f"Error modifying {filepath}: {e}")
    
    def remove_fast_position_merger(self):
        """Special handling to remove FastPositionMerger class"""
        filepath = 'execution/position_merger.py'
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            # Find FastPositionMerger class
            in_fast_class = False
            new_lines = []
            class_indent = None
            
            for line in lines:
                if 'class FastPositionMerger' in line:
                    in_fast_class = True
                    class_indent = len(line) - len(line.lstrip())
                    new_lines.append(f"# Fast approach removed - class commented out\n")
                    new_lines.append(f"# {line}")
                elif in_fast_class:
                    # Check if we're still in the class
                    if line.strip() and not line.startswith(' '):
                        in_fast_class = False
                        new_lines.append(line)
                    elif line.strip() and class_indent is not None:
                        current_indent = len(line) - len(line.lstrip())
                        if current_indent <= class_indent:
                            in_fast_class = False
                            new_lines.append(line)
                        else:
                            new_lines.append(f"# {line}")
                    else:
                        new_lines.append(f"# {line}")
                else:
                    new_lines.append(line)
            
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"✅ Removed FastPositionMerger class from {filepath}")
            
        except Exception as e:
            logger.error(f"Error removing FastPositionMerger: {e}")
    
    def update_conversation_flow(self):
        """Update conversation flow to skip approach selection"""
        filepath = 'handlers/conversation.py'
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # More comprehensive updates
            updates = [
                # Remove approach selection from states
                ('SYMBOL, SIDE, APPROACH_SELECTION,', 'SYMBOL, SIDE,'),
                # Update range definition
                ('GGSHOT_EDIT_VALUES, MARGIN_FAST, MARGIN_CONSERVATIVE = range(14)',
                 'GGSHOT_EDIT_VALUES, MARGIN = range(12)'),
                # Update all returns to skip approach
                ('return APPROACH_SELECTION', 'context.user_data["trading_approach"] = "conservative"\n        return MARGIN'),
                # Update margin state names
                ('MARGIN_CONSERVATIVE', 'MARGIN'),
                ('MARGIN_FAST', 'MARGIN'),
            ]
            
            for old, new in updates:
                content = content.replace(old, new)
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            logger.info("✅ Updated conversation flow")
            
        except Exception as e:
            logger.error(f"Error updating conversation flow: {e}")
    
    def update_stats_tracking(self):
        """Update statistics to remove fast approach tracking"""
        files_to_update = [
            'utils/robust_persistence.py',
            'shared/state.py',
            'dashboard/generator_v2.py'
        ]
        
        for filepath in files_to_update:
            if not os.path.exists(filepath):
                continue
                
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Remove fast trade stats
                content = content.replace('stats_fast_trades', 'stats_fast_trades_removed')
                content = content.replace('"fast_trades":', '"fast_trades_removed":')
                
                with open(filepath, 'w') as f:
                    f.write(content)
                
                logger.info(f"✅ Updated stats in {filepath}")
                
            except Exception as e:
                logger.error(f"Error updating stats in {filepath}: {e}")
    
    def run(self):
        """Run the complete fast approach removal"""
        logger.info("Starting Fast Approach Removal Process...")
        
        # Find files
        files = self.find_files_with_fast_approach()
        logger.info(f"Found {len(files)} files with potential fast approach references")
        
        # Create backups
        self.create_backup(files)
        
        # Get modifications
        modifications = self.get_modifications()
        
        # Apply modifications
        self.apply_modifications(modifications)
        
        # Special handling
        self.remove_fast_position_merger()
        self.update_conversation_flow()
        self.update_stats_tracking()
        
        logger.info("\n✅ Fast approach removal complete!")
        logger.info("The bot now only supports conservative approach trading.")
        logger.info(f"Backups saved in: {self.backup_dir}/")
        
        return True

if __name__ == "__main__":
    remover = FastApproachRemover()
    remover.run()