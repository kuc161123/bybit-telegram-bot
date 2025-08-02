#!/usr/bin/env python3
"""
Simple fix for AI insights - send a test message
"""
import asyncio
import logging
from telegram import Bot
from config.settings import TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_fix():
    """Test if we can identify and fix the problematic content"""
    
    # Sample problematic texts that might appear
    problematic_texts = [
        "Price > $50,000 expected",
        "Momentum < 50% indicates weakness",
        "Risk: Price < support level",
        "Action: Buy if RSI < 30",
        "Volatility > 2% daily"
    ]
    
    print("🔍 Testing problematic content patterns:\n")
    
    for text in problematic_texts:
        print(f"Original: {text}")
        
        # Fix 1: Replace < and > with words
        fixed1 = text.replace('>', ' greater than ')
        fixed1 = fixed1.replace('<', ' less than ')
        print(f"Fixed 1:  {fixed1}")
        
        # Fix 2: Use symbols
        fixed2 = text.replace('>', '→')
        fixed2 = fixed2.replace('<', '←')
        print(f"Fixed 2:  {fixed2}")
        
        # Fix 3: Remove completely
        import re
        fixed3 = re.sub(r'[<>]', '', text)
        print(f"Fixed 3:  {fixed3}")
        
        print("-" * 40)
    
    print("\n✅ Recommendation: Use Fix 1 (replace with words) for clarity")
    print("📌 This preserves the meaning while avoiding HTML parsing issues")

if __name__ == "__main__":
    asyncio.run(test_fix())