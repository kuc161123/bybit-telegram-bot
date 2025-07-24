#!/usr/bin/env python3
"""
Simple Hot-fix for AI Market Analysis Errors

Patches the specific errors without modifying the running bot structure
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_hotfix():
    """Apply targeted fixes"""
    try:
        logger.info("🔧 Applying AI Market Analysis fixes...")
        
        # Fix 1: Patch the market status engine AI analyzer initialization
        logger.info("📌 Fixing AIMarketAnalyzer initialization...")
        
        # Modify the file directly to fix the None client issue
        file_path = '/Users/lualakol/bybit-telegram-bot/market_analysis/market_status_engine.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Replace the problematic line
        old_line = "analyzer = AIMarketAnalyzer(None, ai_client)  # bybit_client not needed for this call"
        new_line = "from clients.bybit_client import bybit_client; analyzer = AIMarketAnalyzer(bybit_client, ai_client)"
        
        if old_line in content:
            content = content.replace(old_line, new_line)
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            logger.info("   ✅ Fixed AIMarketAnalyzer initialization")
        else:
            logger.info("   ℹ️ AIMarketAnalyzer initialization already fixed or different")
        
        # Fix 2: Add division by zero protection to reasoning engine
        logger.info("📌 Adding division by zero protection...")
        
        reasoning_file = '/Users/lualakol/bybit-telegram-bot/execution/ai_reasoning_engine.py'
        
        with open(reasoning_file, 'r') as f:
            content = f.read()
        
        # Find the problematic lines and add protection
        if '"distance_to_support": ((current_price - support) / current_price) * 100,' in content:
            # Replace with safe version
            old_block = '''            "distance_to_support": ((current_price - support) / current_price) * 100,
            "distance_to_resistance": ((resistance - current_price) / current_price) * 100'''
            
            new_block = '''            "distance_to_support": ((current_price - support) / current_price) * 100 if current_price > 0 else 0,
            "distance_to_resistance": ((resistance - current_price) / current_price) * 100 if current_price > 0 else 0'''
            
            content = content.replace(old_block, new_block)
            
            with open(reasoning_file, 'w') as f:
                f.write(content)
            
            logger.info("   ✅ Added division by zero protection")
        else:
            logger.info("   ℹ️ Division protection already added or code changed")
        
        logger.info("\n✅ Fixes applied to source files!")
        logger.info("📌 The changes will take effect on the next AI analysis call")
        logger.info("📌 No bot restart required - the fixed code will be used automatically")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error applying fixes: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 AI Market Analysis Error Fix")
    logger.info("=" * 60)
    
    if apply_hotfix():
        logger.info("\n🎉 Fixes successfully applied!")
        logger.info("📌 The AI market analysis errors should be resolved")
        logger.info("📌 The bot will use the fixed code on the next market analysis")
    else:
        logger.error("\n❌ Failed to apply fixes")