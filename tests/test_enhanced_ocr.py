#!/usr/bin/env python3
"""
Test script for enhanced OCR capabilities
Tests multi-pass extraction, dark mode handling, and mobile screenshot processing
"""
import asyncio
import sys
from PIL import Image
import logging
import os

# Add parent directory to path
sys.path.append('.')

from utils.screenshot_analyzer import screenshot_analyzer
from utils.image_enhancer import enhance_screenshot, enhance_tradingview, enhance_mobile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_multi_pass_extraction():
    """Test multi-pass extraction with different enhancement levels"""
    
    test_cases = [
        {
            "name": "Low Resolution Mobile Screenshot",
            "file": "test_mobile_screenshot.png",
            "symbol": "BTCUSDT",
            "side": "Buy",
            "expected_issues": ["low_res", "mobile"]
        },
        {
            "name": "Dark Mode TradingView",
            "file": "test_dark_screenshot.png",
            "symbol": "ETHUSDT",
            "side": "Sell",
            "expected_issues": ["dark", "low_contrast"]
        },
        {
            "name": "Blurry Screenshot",
            "file": "test_blurry_screenshot.png",
            "symbol": "SOLUSDT",
            "side": "Buy",
            "expected_issues": ["blurry"]
        }
    ]
    
    for test_case in test_cases:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {test_case['name']}")
        logger.info(f"{'='*60}")
        
        if os.path.exists(test_case['file']):
            # Test extraction
            result = await screenshot_analyzer.analyze_trading_screenshot(
                test_case['file'],
                test_case['symbol'],
                test_case['side']
            )
            
            # Log results
            logger.info(f"Success: {result.get('success')}")
            logger.info(f"Confidence: {result.get('confidence', 0):.2f}")
            logger.info(f"Strategy: {result.get('strategy_type', 'unknown')}")
            logger.info(f"Extraction Method: {result.get('extraction_method', 'unknown')}")
            
            if result.get('quality_report'):
                quality = result['quality_report']
                logger.info(f"\nQuality Report:")
                logger.info(f"  - Resolution: {quality.get('resolution')}")
                logger.info(f"  - Is Low Res: {quality.get('is_low_res')}")
                logger.info(f"  - Is Blurry: {quality.get('is_blurry')}")
                logger.info(f"  - Brightness: {quality.get('brightness', {}).get('mean', 'N/A')}")
                logger.info(f"  - Is Dark: {quality.get('brightness', {}).get('is_dark', False)}")
            
            if result.get('parameters'):
                logger.info(f"\nExtracted Parameters:")
                params = result['parameters']
                logger.info(f"  - Entry: {params.get('primary_entry_price', 'N/A')}")
                logger.info(f"  - TP1: {params.get('tp1_price', 'N/A')}")
                logger.info(f"  - SL: {params.get('sl_price', 'N/A')}")
                
            if result.get('validation_errors'):
                logger.warning(f"\nValidation Errors: {result['validation_errors']}")
        else:
            logger.warning(f"Test file not found: {test_case['file']}")

def create_test_images():
    """Create test images with various quality issues"""
    
    # Create dark mode screenshot
    logger.info("Creating dark mode test image...")
    dark_img = Image.new('RGB', (1200, 800), color=(20, 20, 25))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(dark_img)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        font = ImageFont.load_default()
    
    # Dark mode with gray text
    draw.text((50, 100), "BTCUSDT", fill=(150, 150, 150), font=font)
    draw.text((50, 150), "Entry: 65,432.10", fill=(100, 150, 200), font=font)
    draw.text((50, 200), "TP1: 67,000", fill=(100, 200, 100), font=font)
    draw.text((50, 250), "SL: 63,000", fill=(200, 100, 100), font=font)
    
    dark_img.save("test_dark_screenshot.png")
    logger.info("Created: test_dark_screenshot.png")
    
    # Create mobile screenshot (low res)
    logger.info("Creating mobile screenshot...")
    mobile_img = Image.new('RGB', (591, 1280), color='white')
    draw_mobile = ImageDraw.Draw(mobile_img)
    
    # Simulate mobile trading app
    draw_mobile.rectangle([(0, 0), (591, 80)], fill=(50, 50, 50))
    draw_mobile.text((20, 100), "BTCUSDT", fill='black', font=font)
    draw_mobile.text((20, 150), "Buy Long", fill=(0, 150, 0), font=font)
    draw_mobile.text((20, 250), "Entry: 65000", fill='black', font=font)
    draw_mobile.text((20, 300), "TP: 66500", fill=(0, 150, 0), font=font)
    draw_mobile.text((20, 350), "SL: 63500", fill=(150, 0, 0), font=font)
    
    mobile_img.save("test_mobile_screenshot.png")
    logger.info("Created: test_mobile_screenshot.png")
    
    # Create blurry screenshot
    logger.info("Creating blurry screenshot...")
    from PIL import ImageFilter
    clear_img = Image.new('RGB', (1200, 800), color='white')
    draw_clear = ImageDraw.Draw(clear_img)
    
    draw_clear.text((50, 100), "SOLUSDT", fill='black', font=font)
    draw_clear.text((50, 150), "Entry: 145.50", fill='blue', font=font)
    draw_clear.text((50, 200), "TP1: 150.00", fill='green', font=font)
    draw_clear.text((50, 250), "SL: 140.00", fill='red', font=font)
    
    # Apply blur
    blurry_img = clear_img.filter(ImageFilter.GaussianBlur(radius=3))
    blurry_img.save("test_blurry_screenshot.png")
    logger.info("Created: test_blurry_screenshot.png")

async def test_individual_enhancements():
    """Test individual enhancement functions"""
    
    if os.path.exists("test_mobile_screenshot.png"):
        logger.info("\nTesting individual enhancement functions...")
        
        # Load test image
        test_img = Image.open("test_mobile_screenshot.png")
        
        # Test different enhancement levels
        for level in ["quick", "standard", "advanced", "aggressive"]:
            logger.info(f"\nTesting {level} enhancement...")
            enhanced, report = enhance_screenshot(test_img.copy(), level)
            enhanced.save(f"test_enhanced_{level}.png")
            logger.info(f"Saved: test_enhanced_{level}.png")
            logger.info(f"Quality report: {report}")
        
        # Test mobile enhancement
        logger.info("\nTesting mobile-specific enhancement...")
        mobile_enhanced = enhance_mobile(test_img.copy())
        mobile_enhanced.save("test_enhanced_mobile.png")
        logger.info("Saved: test_enhanced_mobile.png")

if __name__ == "__main__":
    # Create test images if they don't exist
    if not all(os.path.exists(f) for f in ["test_dark_screenshot.png", "test_mobile_screenshot.png", "test_blurry_screenshot.png"]):
        create_test_images()
    
    # Run tests
    asyncio.run(test_multi_pass_extraction())
    asyncio.run(test_individual_enhancements())
    
    logger.info("\n✅ Testing complete! Check the generated images to see enhancement results.")