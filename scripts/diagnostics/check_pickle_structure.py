#!/usr/bin/env python3
"""
Check the structure of the pickle file to see available keys
"""
import pickle

def check_pickle_structure():
    """Check what keys are in the pickle file"""
    
    print("PICKLE FILE STRUCTURE")
    print("=" * 50)
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        print(f"Top-level keys: {list(data.keys())}")
        
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"\n{key}: {len(value)} items")
                if len(value) <= 5:
                    for subkey in value.keys():
                        print(f"  - {subkey}")
                else:
                    sample_keys = list(value.keys())[:5]
                    print(f"  Sample keys: {sample_keys}")
            elif isinstance(value, list):
                print(f"\n{key}: {len(value)} items (list)")
            else:
                print(f"\n{key}: {type(value).__name__}")
    
    except Exception as e:
        print(f"Error reading pickle file: {e}")

if __name__ == "__main__":
    check_pickle_structure()