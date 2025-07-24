#!/usr/bin/env python3
"""
Diagnostic script to check your Bybit client setup
"""
import sys
import os

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Checking Bybit client setup...")
print("-" * 50)

# Check pybit version
try:
    import pybit
    print(f"✓ pybit version: {pybit.__version__ if hasattr(pybit, '__version__') else 'Unknown'}")
except ImportError:
    print("✗ pybit is not installed!")
    sys.exit(1)

# Check what's in the clients directory
clients_dir = os.path.join(os.path.dirname(__file__), 'clients')
print(f"\nFiles in clients directory ({clients_dir}):")
if os.path.exists(clients_dir):
    for file in os.listdir(clients_dir):
        print(f"  - {file}")
else:
    print("  ✗ clients directory not found!")

# Try to import bybit_client
print("\nTrying to import bybit_client...")
try:
    from clients.bybit_client import bybit_client
    print("✓ Successfully imported bybit_client")
    
    # Check what type of client it is
    print(f"  Type: {type(bybit_client)}")
    print(f"  Module: {bybit_client.__module__ if hasattr(bybit_client, '__module__') else 'Unknown'}")
    
    # Check available methods
    methods = [m for m in dir(bybit_client) if not m.startswith('_')]
    print(f"  Available methods ({len(methods)} total):")
    for method in methods[:10]:  # Show first 10 methods
        print(f"    - {method}")
    if len(methods) > 10:
        print(f"    ... and {len(methods) - 10} more")
        
except Exception as e:
    print(f"✗ Failed to import bybit_client: {e}")

# Check if it's using unified_trading
print("\nChecking for unified_trading...")
try:
    from pybit.unified_trading import HTTP
    print("✓ pybit.unified_trading.HTTP is available")
except:
    print("✗ pybit.unified_trading.HTTP not found")

print("\n" + "-" * 50)
print("Run this script to diagnose your setup:")