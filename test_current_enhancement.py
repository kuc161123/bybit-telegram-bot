#!/usr/bin/env python3
"""
Test the current enhancement system with a dark mobile screenshot
"""
import asyncio
import sys
import os
from PIL import Image
import logging

# Add parent directory to path
sys.path.append('.')

from utils.screenshot_analyzer import screenshot_analyzer
from utils.image_enhancer import image_enhancer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_current_dark_image():
    """Test current enhancement with the user's dark screenshot"""
    
    # First, create a simulated dark mobile screenshot like the user's
    logger.info("Creating dark mobile screenshot (589x1280)...")
    
    # Create dark image similar to user's screenshot
    dark_img = Image.new('RGB', (589, 1280), color=(15, 15, 20))  # Very dark background
    
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(dark_img)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        font = ImageFont.load_default()
    
    # Simulate TradingView mobile with dark theme
    # Add some text that mimics trading data
    draw.text((20, 100), "LDOUSDT", fill=(120, 120, 130), font=font)
    draw.text((20, 150), "Sell / Short", fill=(180, 50, 50), font=font)
    draw.text((20, 250), "Entry: 1.8950", fill=(150, 150, 160), font=font)
    draw.text((20, 300), "TP1: 1.8500", fill=(50, 180, 50), font=font)
    draw.text((20, 350), "TP2: 1.8300", fill=(50, 180, 50), font=font)
    draw.text((20, 400), "TP3: 1.8100", fill=(50, 180, 50), font=font)
    draw.text((20, 450), "TP4: 1.7900", fill=(50, 180, 50), font=font)
    draw.text((20, 500), "SL: 1.9500", fill=(180, 50, 50), font=font)
    
    # Add some chart-like elements
    draw.line([(50, 600), (539, 650)], fill=(60, 60, 70), width=2)
    draw.line([(50, 700), (539, 680)], fill=(40, 40, 50), width=1)
    
    dark_img.save("test_dark_mobile.png")
    logger.info("Saved: test_dark_mobile.png")
    
    # Test each enhancement level
    logger.info("\nTesting enhancement levels on dark mobile image...")
    
    # Test aggressive enhancement specifically
    logger.info("\n1. Testing AGGRESSIVE enhancement...")
    enhanced_aggressive = await screenshot_analyzer._aggressive_enhance_for_ocr(dark_img.copy())
    enhanced_aggressive.save("test_dark_enhanced_aggressive.png")
    logger.info("Saved: test_dark_enhanced_aggressive.png")
    
    # Test the full multi-pass system
    logger.info("\n2. Testing full multi-pass extraction...")
    result = await screenshot_analyzer.analyze_trading_screenshot(
        "test_dark_mobile.png",
        "LDOUSDT",
        "Sell"
    )
    
    logger.info(f"Extraction success: {result.get('success')}")
    logger.info(f"Confidence: {result.get('confidence', 0)}")
    logger.info(f"Method used: {result.get('extraction_method', 'unknown')}")
    
    if result.get('parameters'):
        params = result['parameters']
        logger.info("\nExtracted parameters:")
        logger.info(f"  Entry: {params.get('primary_entry_price', 'N/A')}")
        logger.info(f"  TP1: {params.get('tp1_price', 'N/A')}")
        logger.info(f"  TP2: {params.get('tp2_price', 'N/A')}")
        logger.info(f"  TP3: {params.get('tp3_price', 'N/A')}")
        logger.info(f"  TP4: {params.get('tp4_price', 'N/A')}")
        logger.info(f"  SL: {params.get('sl_price', 'N/A')}")
    
    # Test individual enhancement methods
    logger.info("\n3. Testing individual enhancement methods...")
    
    # Standard enhancement
    enhanced_std, report_std = image_enhancer.enhance_for_ocr(dark_img.copy(), "standard")
    enhanced_std.save("test_dark_enhanced_standard.png")
    logger.info(f"Standard enhancement - Quality: {report_std}")
    
    # Advanced enhancement
    enhanced_adv, report_adv = image_enhancer.enhance_for_ocr(dark_img.copy(), "advanced")
    enhanced_adv.save("test_dark_enhanced_advanced.png")
    logger.info(f"Advanced enhancement - Quality: {report_adv}")
    
    # Mobile enhancement
    from utils.image_enhancer import enhance_mobile
    enhanced_mobile = enhance_mobile(dark_img.copy())
    enhanced_mobile.save("test_dark_enhanced_mobile.png")
    logger.info("Mobile enhancement saved")
    
    # Dark mode specific enhancement
    if image_enhancer._is_dark_mode_screenshot(dark_img):
        logger.info("\n4. Testing dark mode specific enhancement...")
        enhanced_dark = image_enhancer._enhance_dark_mode_screenshot(dark_img.copy())
        enhanced_dark.save("test_dark_enhanced_darkmode.png")
        logger.info("Dark mode enhancement saved")
    
    logger.info("\n✅ Testing complete! Check the generated images:")
    logger.info("  - test_dark_mobile.png (original)")
    logger.info("  - test_dark_enhanced_aggressive.png")
    logger.info("  - test_dark_enhanced_standard.png")
    logger.info("  - test_dark_enhanced_advanced.png")
    logger.info("  - test_dark_enhanced_mobile.png")
    logger.info("  - test_dark_enhanced_darkmode.png")

if __name__ == "__main__":
    asyncio.run(test_current_dark_image())