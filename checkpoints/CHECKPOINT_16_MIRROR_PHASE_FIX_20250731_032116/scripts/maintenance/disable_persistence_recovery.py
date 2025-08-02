#!/usr/bin/env python3
"""
Temporarily disable persistence recovery in the bot to prevent backup restoration
"""

import os

def create_recovery_override():
    """Create a file that tells the bot not to restore from backups"""
    
    override_content = {
        "disable_recovery": True,
        "reason": "false_tp_fix_protection",
        "message": "Persistence recovery disabled to protect false TP fix"
    }
    
    # Create override file
    with open('.disable_persistence_recovery', 'w') as f:
        import json
        json.dump(override_content, f, indent=2)
    
    print("✅ Created .disable_persistence_recovery file")
    print("This will prevent the bot from restoring old backups")
    print("\nTo re-enable recovery later:")
    print("  rm .disable_persistence_recovery")

if __name__ == "__main__":
    create_recovery_override()