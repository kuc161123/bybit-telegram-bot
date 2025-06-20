#!/usr/bin/env python3
"""
AI client initialization and management.
"""
import logging
from config.settings import LLM_PROVIDER, OPENAI_API_KEY

logger = logging.getLogger(__name__)

# Import OpenAI library
try:
    from openai import OpenAI
    openai_available = True
except ImportError:
    openai_available = False
    print("OpenAI library not found. AI features with OpenAI will be disabled. Run 'pip install openai'")

def create_openai_client():
    """Create and return an OpenAI client if configured"""
    global LLM_PROVIDER
    
    if LLM_PROVIDER == "openai":
        if not openai_available:
            logger.error("LLM_PROVIDER 'openai' but library not installed. Falling back to stub.")
            LLM_PROVIDER = "stub"
            return None
        elif not OPENAI_API_KEY:
            logger.warning("LLM_PROVIDER 'openai' but OPENAI_API_KEY not set. Using stub.")
            LLM_PROVIDER = "stub"
            return None
        else:
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)  
                logger.info("OpenAI client configured successfully.")
                return client
            except Exception as e_openai_config:
                logger.error(f"Failed to configure OpenAI client: {e_openai_config}. Falling back to stub.")
                LLM_PROVIDER = "stub"
                return None
    elif LLM_PROVIDER not in ["stub"]:
        logger.warning(f"LLM_PROVIDER '{LLM_PROVIDER}' not recognized. Using 'stub'.")
        LLM_PROVIDER = "stub"
        return None
    
    return None

# Global client instance
openai_client = create_openai_client()