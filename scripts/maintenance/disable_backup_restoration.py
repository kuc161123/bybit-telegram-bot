#!/usr/bin/env python3
"""
Create a flag to disable backup restoration temporarily
"""

import json
from datetime import datetime

def create_no_restore_flag():
    """Create a flag file to prevent backup restoration"""
    
    flag_data = {
        "no_restore": True,
        "reason": "false_tp_detection_fix_applied",
        "created_at": datetime.now().isoformat(),
        "description": "Prevents restoration from old backups containing incorrect mirror monitor data",
        "can_remove_after": "2025-07-10",  # Give it a few days to ensure stability
        "fixed_issues": [
            "Mirror monitors had main account position sizes",
            "remaining_size pointed to wrong account values",
            "Fill tracker contained incorrect cumulative percentages"
        ]
    }
    
    # Create the flag file
    with open('.no_backup_restore', 'w') as f:
        json.dump(flag_data, f, indent=2)
    
    print("✅ Created .no_backup_restore flag file")
    print("This will prevent the bot from restoring old backups")
    print("\nTo re-enable backup restoration after confirming the fix:")
    print("  rm .no_backup_restore")
    
    # Also create a persistent marker in the pickle file
    import pickle
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    # Add a marker to indicate the fix has been applied
    data['bot_data']['false_tp_fix_applied'] = {
        'version': 2,
        'applied_at': datetime.now().isoformat(),
        'description': 'Mirror monitors fixed to use correct position sizes'
    }
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print("\n✅ Added persistent marker to pickle file")
    print("The bot will know that the false TP fix has been applied")

if __name__ == "__main__":
    create_no_restore_flag()