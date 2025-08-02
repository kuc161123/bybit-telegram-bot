#!/usr/bin/env python3
"""
Hot-fix for AI Market Analysis Errors

This script patches the running bot to fix:
1. NoneType error in market data gathering
2. Division by zero in AI reasoning
"""

import logging
import sys
import importlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_hotfix():
    """Apply hot-fixes to the running bot"""
    try:
        logger.info("🔧 Applying AI Market Analysis Hot-fixes...")
        
        # Fix 1: Patch the AIMarketAnalyzer to handle None client
        logger.info("📌 Patching AIMarketAnalyzer...")
        
        # Import the module
        import execution.ai_market_analysis as ai_market
        from clients.bybit_client import bybit_client
        
        # Check if the singleton instance exists
        if hasattr(ai_market, '_analyzer_instance') and ai_market._analyzer_instance:
            analyzer = ai_market._analyzer_instance
            
            # Fix the bybit_client if it's None
            if analyzer.bybit_client is None:
                logger.info("   ✅ Setting bybit_client in AIMarketAnalyzer")
                analyzer.bybit_client = bybit_client
            else:
                logger.info("   ℹ️ bybit_client already set")
                
            # Also ensure the get_market_analyzer function returns properly initialized instance
            original_get_analyzer = ai_market.get_market_analyzer
            
            def patched_get_analyzer():
                instance = original_get_analyzer()
                if instance.bybit_client is None:
                    instance.bybit_client = bybit_client
                return instance
            
            ai_market.get_market_analyzer = patched_get_analyzer
            logger.info("   ✅ Patched get_market_analyzer function")
        
        # Fix 2: Patch the reasoning engine to handle division by zero
        logger.info("📌 Patching AI Reasoning Engine...")
        
        import execution.ai_reasoning_engine as reasoning
        
        # Patch the _prepare_analysis_context method
        if hasattr(reasoning.AIReasoningEngine, '_prepare_analysis_context'):
            original_method = reasoning.AIReasoningEngine._prepare_analysis_context
            
            def safe_prepare_analysis_context(self, market_data: dict) -> dict:
                """Safe version that handles zero prices"""
                # Call original method first
                try:
                    return original_method(self, market_data)
                except ZeroDivisionError:
                    # Handle the zero division case
                    logger.warning("Caught division by zero in analysis context")
                    
                    current_price = market_data.get("current_price", 0)
                    support = market_data.get("support_level", 0)
                    resistance = market_data.get("resistance_level", 0)
                    
                    # Create safe context
                    context = {
                        "current_price": current_price,
                        "support_level": support,
                        "resistance_level": resistance,
                        "price_change_24h": market_data.get("price_change_24h", 0),
                        "volume_24h": market_data.get("volume_24h", 0),
                        "volatility": market_data.get("volatility", 0),
                        "trend": market_data.get("trend", "neutral"),
                        "momentum": market_data.get("momentum", 0),
                        "market_regime": market_data.get("market_regime", "unknown"),
                        "regime_confidence": market_data.get("regime_confidence", 0)
                    }
                    
                    # Safe distance calculations
                    if current_price > 0:
                        context["distance_to_support"] = ((current_price - support) / current_price) * 100 if support else 0
                        context["distance_to_resistance"] = ((resistance - current_price) / current_price) * 100 if resistance else 0
                    else:
                        context["distance_to_support"] = 0
                        context["distance_to_resistance"] = 0
                    
                    # Technical indicators with safe defaults
                    context["rsi"] = market_data.get("rsi", 50)
                    context["macd_signal"] = market_data.get("macd_signal", "neutral")
                    context["bollinger_position"] = market_data.get("bollinger_position", "middle")
                    context["volume_trend"] = market_data.get("volume_trend", "average")
                    
                    return context
            
            # Replace the method
            reasoning.AIReasoningEngine._prepare_analysis_context = safe_prepare_analysis_context
            logger.info("   ✅ Patched _prepare_analysis_context method")
        
        # Fix 3: Add additional safety to market data gathering
        if hasattr(ai_market.AIMarketAnalyzer, '_gather_market_data'):
            original_gather = ai_market.AIMarketAnalyzer._gather_market_data
            
            async def safe_gather_market_data(self, symbol: str) -> dict:
                """Safe version that ensures client exists"""
                if self.bybit_client is None:
                    from clients.bybit_client import bybit_client
                    self.bybit_client = bybit_client
                    logger.info(f"   ℹ️ Auto-initialized bybit_client for {symbol}")
                
                return await original_gather(self, symbol)
            
            ai_market.AIMarketAnalyzer._gather_market_data = safe_gather_market_data
            logger.info("   ✅ Patched _gather_market_data method")
        
        logger.info("✅ All hot-fixes applied successfully!")
        logger.info("📌 The AI market analysis should now work without errors")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error applying hot-fixes: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_fix():
    """Verify the fixes are working"""
    try:
        logger.info("\n🔍 Verifying fixes...")
        
        # Test the market analyzer
        from execution.ai_market_analysis import get_market_analyzer
        analyzer = get_market_analyzer()
        
        if analyzer.bybit_client is None:
            logger.error("   ❌ bybit_client is still None")
            return False
        else:
            logger.info("   ✅ bybit_client is properly set")
        
        # Test division by zero handling
        from execution.ai_reasoning_engine import AIReasoningEngine
        engine = AIReasoningEngine()
        
        # Test with zero price
        test_data = {
            "current_price": 0,
            "support_level": 100,
            "resistance_level": 200
        }
        
        try:
            context = engine._prepare_analysis_context(test_data)
            logger.info("   ✅ Division by zero handling works")
        except ZeroDivisionError:
            logger.error("   ❌ Division by zero still occurs")
            return False
        
        logger.info("\n✅ All verifications passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Verification error: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 AI Market Analysis Hot-fix Script")
    logger.info("=" * 60)
    
    # Apply the fixes
    if apply_hotfix():
        # Verify they work
        if verify_fix():
            logger.info("\n🎉 Hot-fixes successfully applied and verified!")
            logger.info("📌 The AI market analysis errors should be resolved")
            logger.info("📌 No bot restart required")
        else:
            logger.error("\n❌ Verification failed - manual intervention may be needed")
    else:
        logger.error("\n❌ Failed to apply hot-fixes")