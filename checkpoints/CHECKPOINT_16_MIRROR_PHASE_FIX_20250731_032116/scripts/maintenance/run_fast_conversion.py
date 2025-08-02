#!/usr/bin/env python3
"""
Complete JTOUSDT Fast Conversion Process
Runs conversion and verification in sequence
"""

import asyncio
import subprocess
import sys
import os

async def run_conversion_process():
    """Run the complete conversion and verification process"""
    
    print("🚀 Starting JTOUSDT Fast-Only Conversion Process...")
    print("="*80)
    
    # Step 1: Run the conversion
    print("\n📍 STEP 1: Running conversion script...")
    try:
        result = subprocess.run([sys.executable, "convert_to_fast_only.py"], 
                              capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ Conversion completed successfully!")
            print(result.stdout)
        else:
            print("❌ Conversion failed!")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running conversion: {e}")
        return False
    
    # Step 2: Wait a moment for orders to settle
    print("\n⏱️ Waiting for orders to settle...")
    await asyncio.sleep(3)
    
    # Step 3: Run verification
    print("\n📍 STEP 2: Running verification script...")
    try:
        result = subprocess.run([sys.executable, "verify_fast_cleanup.py"], 
                              capture_output=True, text=True, cwd=os.getcwd())
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Verification completed!")
        else:
            print("⚠️ Verification found issues!")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Error running verification: {e}")
        return False
    
    print("\n🎉 Process completed! Check the verification results above.")
    return True

if __name__ == "__main__":
    asyncio.run(run_conversion_process())