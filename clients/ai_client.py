#!/usr/bin/env python3
"""
AI client initialization and management.
"""
import os
import logging
from config.settings import LLM_PROVIDER, OPENAI_API_KEY, AI_MODEL

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

# AI Client wrapper class for compatibility
class AIClient:
    """Wrapper class for OpenAI client"""

    def __init__(self, client=None):
        self.client = client or openai_client
        self.llm_provider = LLM_PROVIDER

    async def analyze_market(self, prompt: str) -> str:
        """Analyze market using AI"""
        if self.llm_provider == "stub" or not self.client:
            return "AI analysis unavailable - no API key configured"

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a cryptocurrency trading analyst providing concise market insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return f"AI analysis error: {str(e)}"

    async def analyze_market_advanced(self, prompt: str, model: str = None) -> str:
        """Advanced market analysis using GPT-4 for enhanced reasoning"""
        if self.llm_provider == "stub" or not self.client:
            return "AI analysis unavailable - no API key configured"

        # Use configured model if not specified
        if model is None:
            model = AI_MODEL

        try:
            # Check if GPT-4 is enabled
            enable_gpt4 = os.getenv("ENABLE_GPT4_REASONING", "true").lower() == "true"
            if not enable_gpt4:
                # Fall back to regular analysis
                return await self.analyze_market(prompt)

            # Use GPT-4 for advanced reasoning
            logger.info(f"🤖 Using AI model: {model} for advanced analysis")
            response = self.client.chat.completions.create(
                model=model,  # Uses configured AI_MODEL by default
                messages=[
                    {"role": "system", "content": "You are an expert cryptocurrency trading analyst with deep market knowledge. Provide detailed, actionable insights with clear reasoning."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,  # Increased for deeper analysis
                temperature=0.3  # Lower temperature for more consistent analysis
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"GPT-4 analysis failed, falling back to GPT-3.5: {e}")
            # Fallback to GPT-3.5
            return await self.analyze_market(prompt)

# Helper function to get AI client
def get_ai_client():
    """Get AI client instance"""
    return AIClient(openai_client)