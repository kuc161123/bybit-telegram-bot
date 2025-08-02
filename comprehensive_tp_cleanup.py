#!/usr/bin/env python3
"""
Comprehensive TP2-4 Remnant Cleanup Script
==========================================

This script removes all TP2-4 remnants from the bot's pickle data structure
to prevent runtime errors after the single TP conversion.

CRITICAL ACTIONS:
- Remove TP2-4 orders from enhanced_tp_sl_monitors
- Clean chat_data TP2-4 price references
- Handle tp_number fields > 1
- Update order_link_ids containing TP2-4 references

SAFETY FEATURES:
- Creates timestamped backup before cleanup
- Comprehensive validation after cleanup
- Detailed logging of all changes
- Rollback capability
"""

import pickle
import time
import shutil
from pathlib import Path
from typing import Dict, Any, List

class TPRemnantCleaner:
    def __init__(self, pickle_path: str):
        self.pickle_path = pickle_path
        self.backup_path = f"{pickle_path}.backup_tp_cleanup_{int(time.time())}"
        self.changes_made = []
        
    def create_backup(self):
        """Create timestamped backup of pickle file."""
        print(f"🔄 Creating backup: {self.backup_path}")
        shutil.copy2(self.pickle_path, self.backup_path)
        print(f"✅ Backup created successfully")
    
    def load_data(self) -> Dict[str, Any]:
        """Load pickle data."""
        print("📂 Loading pickle data...")
        with open(self.pickle_path, 'rb') as f:
            data = pickle.load(f)
        print("✅ Data loaded successfully")
        return data
    
    def save_data(self, data: Dict[str, Any]):
        """Save cleaned data back to pickle file."""
        print("💾 Saving cleaned data...")
        with open(self.pickle_path, 'wb') as f:
            pickle.dump(data, f)
        print("✅ Data saved successfully")
    
    def clean_chat_data(self, data: Dict[str, Any]) -> int:
        """Clean TP2-4 references from chat_data."""
        print("🧹 Cleaning chat_data TP2-4 references...")
        changes = 0
        
        chat_data = data.get('chat_data', {})
        tp_fields_to_remove = ['tp2_price', 'tp3_price', 'tp4_price']
        
        for chat_id, chat_info in chat_data.items():
            if not isinstance(chat_info, dict):
                continue
                
            for field in tp_fields_to_remove:
                if field in chat_info:
                    removed_value = chat_info[field]
                    del chat_info[field]
                    change = f"Removed {field}={removed_value} from chat {chat_id}"
                    self.changes_made.append(change)
                    print(f"  ✓ {change}")
                    changes += 1
        
        print(f"✅ Chat data cleanup: {changes} changes made")
        return changes
    
    def clean_monitor_data(self, data: Dict[str, Any]) -> int:
        """Clean TP2-4 orders from enhanced_tp_sl_monitors."""
        print("🧹 Cleaning enhanced_tp_sl_monitors TP2-4 orders...")
        changes = 0
        
        monitor_data = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})\n        if not monitor_data:\n            monitor_data = data.get('enhanced_tp_sl_monitors', {})\n        \n        if not monitor_data:\n            print(\"⚠️  No monitor data found in pickle file\")\n            return 0\n        \n        for monitor_key, monitor_info in monitor_data.items():\n            if not isinstance(monitor_info, dict):\n                continue\n                \n            tp_orders = monitor_info.get('tp_orders', {})\n            if not isinstance(tp_orders, dict):\n                continue\n            \n            orders_to_remove = []\n            \n            # Find TP2-4 orders to remove\n            for order_id, order_info in tp_orders.items():\n                if not isinstance(order_info, dict):\n                    continue\n                \n                # Check tp_number field\n                tp_number = order_info.get('tp_number')\n                if tp_number in [2, 3, 4]:\n                    orders_to_remove.append((order_id, f\"tp_number={tp_number}\"))\n                    continue\n                \n                # Check order_link_id for TP2-4 references\n                order_link_id = order_info.get('order_link_id', '')\n                if any(tp_ref in str(order_link_id) for tp_ref in ['TP2_', 'TP3_', 'TP4_']):\n                    orders_to_remove.append((order_id, f\"order_link_id={order_link_id}\"))\n            \n            # Remove identified orders\n            for order_id, reason in orders_to_remove:\n                del tp_orders[order_id]\n                change = f\"Removed TP2-4 order {order_id} from {monitor_key} ({reason})\"\n                self.changes_made.append(change)\n                print(f\"  ✓ {change}\")\n                changes += 1\n        \n        print(f\"✅ Monitor data cleanup: {changes} changes made\")\n        return changes\n    \n    def validate_cleanup(self, data: Dict[str, Any]) -> Dict[str, Any]:\n        \"\"\"Validate that all TP2-4 references have been removed.\"\"\"\n        print(\"🔍 Validating cleanup results...\")\n        \n        validation_results = {\n            'chat_tp_references': 0,\n            'monitor_tp_orders': 0,\n            'tp_order_links': 0,\n            'remaining_issues': []\n        }\n        \n        # Check chat_data\n        chat_data = data.get('chat_data', {})\n        for chat_id, chat_info in chat_data.items():\n            if isinstance(chat_info, dict):\n                for key in chat_info.keys():\n                    if any(tp_ref in str(key).lower() for tp_ref in ['tp2', 'tp3', 'tp4']):\n                        validation_results['chat_tp_references'] += 1\n                        validation_results['remaining_issues'].append(f\"chat_data[{chat_id}][{key}]\")\n        \n        # Check monitor data\n        monitor_data = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})\n        if not monitor_data:\n            monitor_data = data.get('enhanced_tp_sl_monitors', {})\n            \n        for monitor_key, monitor_info in monitor_data.items():\n            if isinstance(monitor_info, dict):\n                tp_orders = monitor_info.get('tp_orders', {})\n                if isinstance(tp_orders, dict):\n                    for order_id, order_info in tp_orders.items():\n                        if isinstance(order_info, dict):\n                            # Check tp_number\n                            tp_number = order_info.get('tp_number')\n                            if tp_number in [2, 3, 4]:\n                                validation_results['monitor_tp_orders'] += 1\n                                validation_results['remaining_issues'].append(\n                                    f\"enhanced_tp_sl_monitors[{monitor_key}][tp_orders][{order_id}][tp_number]={tp_number}\"\n                                )\n                            \n                            # Check order_link_id\n                            order_link_id = str(order_info.get('order_link_id', ''))\n                            if any(tp_ref in order_link_id for tp_ref in ['TP2_', 'TP3_', 'TP4_']):\n                                validation_results['tp_order_links'] += 1\n                                validation_results['remaining_issues'].append(\n                                    f\"enhanced_tp_sl_monitors[{monitor_key}][tp_orders][{order_id}][order_link_id]={order_link_id}\"\n                                )\n        \n        total_issues = (validation_results['chat_tp_references'] + \n                       validation_results['monitor_tp_orders'] + \n                       validation_results['tp_order_links'])\n        \n        if total_issues == 0:\n            print(\"✅ Validation passed: No TP2-4 references found\")\n        else:\n            print(f\"⚠️  Validation found {total_issues} remaining issues:\")\n            for issue in validation_results['remaining_issues']:\n                print(f\"  - {issue}\")\n        \n        return validation_results\n    \n    def print_summary(self, chat_changes: int, monitor_changes: int, validation: Dict[str, Any]):\n        \"\"\"Print comprehensive cleanup summary.\"\"\"\n        print(\"\\n\" + \"=\" * 60)\n        print(\"📋 CLEANUP SUMMARY\")\n        print(\"=\" * 60)\n        print(f\"Chat data changes: {chat_changes}\")\n        print(f\"Monitor data changes: {monitor_changes}\")\n        print(f\"Total changes: {len(self.changes_made)}\")\n        print(f\"Backup created: {self.backup_path}\")\n        \n        if validation['remaining_issues']:\n            print(f\"\\n⚠️  WARNING: {len(validation['remaining_issues'])} issues remain\")\n            print(\"Manual review may be required for:\")\n            for issue in validation['remaining_issues'][:5]:  # Show first 5\n                print(f\"  - {issue}\")\n            if len(validation['remaining_issues']) > 5:\n                print(f\"  ... and {len(validation['remaining_issues']) - 5} more\")\n        else:\n            print(\"\\n✅ SUCCESS: All TP2-4 references removed\")\n        \n        print(f\"\\n📄 DETAILED CHANGES:\")\n        for i, change in enumerate(self.changes_made, 1):\n            print(f\"{i:2d}. {change}\")\n    \n    def run_cleanup(self) -> bool:\n        \"\"\"Run comprehensive cleanup process.\"\"\"\n        print(\"🚀 Starting comprehensive TP2-4 remnant cleanup...\")\n        print(\"=\" * 60)\n        \n        try:\n            # Create backup\n            self.create_backup()\n            \n            # Load data\n            data = self.load_data()\n            \n            # Perform cleanup\n            chat_changes = self.clean_chat_data(data)\n            monitor_changes = self.clean_monitor_data(data)\n            \n            # Save cleaned data\n            self.save_data(data)\n            \n            # Validate results\n            validation = self.validate_cleanup(data)\n            \n            # Print summary\n            self.print_summary(chat_changes, monitor_changes, validation)\n            \n            return len(validation['remaining_issues']) == 0\n            \n        except Exception as e:\n            print(f\"❌ Cleanup failed: {e}\")\n            print(f\"🔄 Restore from backup: {self.backup_path}\")\n            return False

def main():\n    \"\"\"Main function to run cleanup.\"\"\"\n    pickle_path = \"/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl\"\n    \n    if not Path(pickle_path).exists():\n        print(f\"❌ Pickle file not found: {pickle_path}\")\n        return\n    \n    cleaner = TPRemnantCleaner(pickle_path)\n    success = cleaner.run_cleanup()\n    \n    if success:\n        print(\"\\n🎉 Cleanup completed successfully!\")\n        print(\"The bot should now be safe to run with single TP configuration.\")\n    else:\n        print(\"\\n⚠️  Cleanup completed with warnings.\")\n        print(\"Manual review of remaining issues may be required.\")\n    \n    print(f\"\\n💡 ROLLBACK: If issues occur, restore from backup:\")\n    print(f\"   cp {cleaner.backup_path} {pickle_path}\")\n\nif __name__ == '__main__':\n    main()