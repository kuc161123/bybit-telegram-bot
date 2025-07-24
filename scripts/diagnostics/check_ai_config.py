#!/usr/bin/env python3
"""
Quick check to verify AI configuration is active
"""
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_ai_config():
    """Check if AI features are properly configured"""
    logger.info("🔍 Checking AI Configuration")
    logger.info("=" * 50)
    
    # Check environment variables
    openai_key = os.getenv("OPENAI_API_KEY")
    llm_provider = os.getenv("LLM_PROVIDER", "stub")
    enable_gpt4 = os.getenv("ENABLE_GPT4_REASONING", "true").lower() == "true"
    
    logger.info(f"OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Not set'}")
    logger.info(f"LLM_PROVIDER: {llm_provider} {'✅' if llm_provider == 'openai' else '⚠️ (should be openai)'}")
    logger.info(f"ENABLE_GPT4_REASONING: {enable_gpt4} {'✅' if enable_gpt4 else '⚠️'}")
    
    if openai_key and llm_provider == "openai":
        logger.info("\n✅ AI features are properly configured!")
        logger.info("🤖 GPT-4 market analysis will be available in the dashboard")
        
        # Test AI client initialization
        try:
            from clients.ai_client import get_ai_client
            ai_client = get_ai_client()
            
            if ai_client.llm_provider == "openai":
                logger.info("✅ AI client initialized successfully")
            else:
                logger.warning(f"⚠️ AI client provider is '{ai_client.llm_provider}', expected 'openai'")
                
        except Exception as e:
            logger.error(f"❌ Error initializing AI client: {e}")
    else:
        logger.warning("\n⚠️ AI features are NOT configured")
        logger.info("To enable GPT-4 market analysis:")
        logger.info("1. Set OPENAI_API_KEY in your .env file")
        logger.info("2. Set LLM_PROVIDER=openai")
        logger.info("3. Restart the bot to load environment variables")
    
    logger.info("\n" + "=" * 50)
    logger.info("To refresh dashboard: Use /start command in Telegram")

if __name__ == "__main__":
    check_ai_config()