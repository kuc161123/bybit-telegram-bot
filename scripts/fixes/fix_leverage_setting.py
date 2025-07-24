#!/usr/bin/env python3
"""
Script to add leverage setting functionality to the bot.

This will:
1. Add a helper function to set leverage before placing orders
2. Show where to integrate it in the trader.py file
3. Create a patch that can be applied
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# The function to add to bybit_helpers.py
LEVERAGE_FUNCTION = '''
async def set_symbol_leverage(symbol: str, leverage: int, client=None) -> bool:
    """
    Set leverage for a symbol before placing orders.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        leverage: Leverage value (e.g., 10 for 10x)
        client: Bybit client instance (defaults to main client)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if client is None:
        client = bybit_client
        
    try:
        logger.info(f"⚡ Setting leverage for {symbol} to {leverage}x...")
        
        response = await api_call_with_retry(
            lambda: client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            ),
            timeout=30
        )
        
        if response and response.get('retCode') == 0:
            logger.info(f"✅ Successfully set {symbol} leverage to {leverage}x")
            return True
        else:
            logger.error(f"❌ Failed to set leverage for {symbol}: {response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error setting leverage for {symbol}: {e}")
        return False
'''

# The modification needed in trader.py (in execute_fast_market function)
TRADER_MODIFICATION = '''
# Add this BEFORE placing any orders (around line 404 in execute_fast_market):

            # Set leverage before placing orders
            leverage_set = await set_symbol_leverage(symbol, leverage)
            if not leverage_set:
                self.logger.warning(f"⚠️ Failed to set leverage, continuing with existing leverage")

# Similarly, add in execute_conservative_with_limit (around line 1476):

            # Set leverage before placing orders
            leverage_set = await set_symbol_leverage(symbol, leverage)
            if not leverage_set:
                self.logger.warning(f"⚠️ Failed to set leverage, continuing with existing leverage")
'''

# Create patch file
PATCH_CONTENT = '''--- a/clients/bybit_helpers.py
+++ b/clients/bybit_helpers.py
@@ -2115,6 +2115,39 @@ async def periodic_order_cleanup_task():
         await asyncio.sleep(300)  # Run every 5 minutes
 
 
+async def set_symbol_leverage(symbol: str, leverage: int, client=None) -> bool:
+    """
+    Set leverage for a symbol before placing orders.
+    
+    Args:
+        symbol: Trading symbol (e.g., 'BTCUSDT')
+        leverage: Leverage value (e.g., 10 for 10x)
+        client: Bybit client instance (defaults to main client)
+        
+    Returns:
+        bool: True if successful, False otherwise
+    """
+    if client is None:
+        client = bybit_client
+        
+    try:
+        logger.info(f"⚡ Setting leverage for {symbol} to {leverage}x...")
+        
+        response = await api_call_with_retry(
+            lambda: client.set_leverage(
+                category="linear",
+                symbol=symbol,
+                buyLeverage=str(leverage),
+                sellLeverage=str(leverage)
+            ),
+            timeout=30
+        )
+        
+        if response and response.get('retCode') == 0:
+            logger.info(f"✅ Successfully set {symbol} leverage to {leverage}x")
+            return True
+        else:
+            logger.error(f"❌ Failed to set leverage for {symbol}: {response}")
+            return False
+            
+    except Exception as e:
+        logger.error(f"❌ Error setting leverage for {symbol}: {e}")
+        return False
+
+
 def calculate_order_metrics(order: Dict, current_price: float) -> Dict[str, float]:
--- a/execution/trader.py
+++ b/execution/trader.py
@@ -25,6 +25,7 @@ from clients.bybit_helpers import (
     cancel_order_with_retry,
     get_symbol_info,
     get_current_price,
+    set_symbol_leverage,
     validate_order_parameters,
     get_correct_position_idx,
     add_trade_group_id,
@@ -401,6 +402,11 @@ class Trader:
             self.logger.info(f"Margin amount: ${margin_amount}")
             self.logger.info(f"Position size: {position_size} {symbol}")
             
+            # Set leverage before placing orders
+            leverage_set = await set_symbol_leverage(symbol, leverage)
+            if not leverage_set:
+                self.logger.warning(f"⚠️ Failed to set leverage, continuing with existing leverage")
+            
             position_size = margin_amount * leverage
             
             # Get symbol info for precision
@@ -1473,6 +1479,11 @@ class Trader:
             self.logger.info(f"Total position size: {total_position_size} {symbol}")
             self.logger.info(f"Adjusted position size: {adjusted_position_size} {symbol}")
             
+            # Set leverage before placing orders
+            leverage_set = await set_symbol_leverage(symbol, leverage)
+            if not leverage_set:
+                self.logger.warning(f"⚠️ Failed to set leverage, continuing with existing leverage")
+            
             total_position_size = margin_amount * leverage
             
             # Store approach type for monitoring
'''


def main():
    """Generate fix documentation"""
    print("=" * 80)
    print("LEVERAGE SETTING FIX")
    print("=" * 80)
    print()
    
    print("📋 PROBLEM IDENTIFIED:")
    print("- The bot is NOT setting leverage before placing orders")
    print("- Orders use whatever leverage was last set manually on the symbol")
    print("- This causes mismatch between selected leverage and actual position leverage")
    print()
    
    print("🔧 SOLUTION:")
    print("1. Add set_symbol_leverage() function to bybit_helpers.py")
    print("2. Call it before placing orders in trader.py")
    print("3. This ensures leverage matches user selection")
    print()
    
    print("📁 FILES TO MODIFY:")
    print("1. clients/bybit_helpers.py - Add the leverage setting function")
    print("2. execution/trader.py - Call the function before placing orders")
    print()
    
    # Save the patch file
    patch_path = "patches/fix_leverage_setting.patch"
    os.makedirs("patches", exist_ok=True)
    
    with open(patch_path, 'w') as f:
        f.write(PATCH_CONTENT)
    
    print(f"✅ Patch file created: {patch_path}")
    print()
    print("🚀 TO APPLY THE FIX:")
    print(f"   git apply {patch_path}")
    print()
    print("Or manually:")
    print("1. Add the set_symbol_leverage function to clients/bybit_helpers.py")
    print("2. Import it in execution/trader.py")
    print("3. Call it before placing orders in execute_fast_market and execute_conservative_with_limit")
    print()
    print("📝 FUNCTION TO ADD TO bybit_helpers.py:")
    print("-" * 80)
    print(LEVERAGE_FUNCTION)
    print("-" * 80)
    print()
    print("📝 MODIFICATIONS FOR trader.py:")
    print("-" * 80)
    print(TRADER_MODIFICATION)
    print("-" * 80)


if __name__ == "__main__":
    main()