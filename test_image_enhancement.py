#!/usr/bin/env python3
"""
Test script for image enhancement capabilities
Demonstrates different enhancement levels and their effects
"""
import asyncio
import sys
from PIL import Image
import logging

# Add parent directory to path
sys.path.append('.')

from utils.image_enhancer import enhance_screenshot, enhance_tradingview

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhancement():
    """Test different enhancement levels"""
    
    # Test with a sample image (you'll need to provide your own test image)
    test_image_path = "test_screenshot.png"  # Replace with your test image
    
    try:
        # Load test image
        original = Image.open(test_image_path)
        logger.info(f"Loaded test image: {original.size} {original.mode}")
        
        # Test quick enhancement
        logger.info("\n1. Testing QUICK enhancement...")
        quick_enhanced, quick_report = enhance_screenshot(original.copy(), "quick")
        logger.info(f"Quick enhancement report: {quick_report}")
        quick_enhanced.save("test_enhanced_quick.png")
        
        # Test standard enhancement
        logger.info("\n2. Testing STANDARD enhancement...")
        standard_enhanced, standard_report = enhance_screenshot(original.copy(), "standard")
        logger.info(f"Standard enhancement report: {standard_report}")
        standard_enhanced.save("test_enhanced_standard.png")
        
        # Test advanced enhancement
        logger.info("\n3. Testing ADVANCED enhancement...")
        advanced_enhanced, advanced_report = enhance_screenshot(original.copy(), "advanced")
        logger.info(f"Advanced enhancement report: {advanced_report}")
        advanced_enhanced.save("test_enhanced_advanced.png")
        
        # Test TradingView specific enhancement
        logger.info("\n4. Testing TradingView-specific enhancement...")
        tv_enhanced = enhance_tradingview(original.copy())
        tv_enhanced.save("test_enhanced_tradingview.png")
        
        logger.info("\n✅ Enhancement tests complete!")
        logger.info("Check the output files:")
        logger.info("- test_enhanced_quick.png")
        logger.info("- test_enhanced_standard.png")
        logger.info("- test_enhanced_advanced.png")
        logger.info("- test_enhanced_tradingview.png")
        
        # Quality analysis summary
        if quick_report["is_blurry"]:
            logger.warning("⚠️ Image appears to be blurry")
        if quick_report["is_low_res"]:
            logger.warning("⚠️ Image resolution is below recommended")
        if quick_report["brightness"]["has_low_contrast"]:
            logger.warning("⚠️ Image has low contrast")
            
    except FileNotFoundError:
        logger.error(f"Test image not found: {test_image_path}")
        logger.info("Please provide a test screenshot as 'test_screenshot.png'")
    except Exception as e:
        logger.error(f"Error during enhancement test: {e}")

def create_sample_image():
    """Create a sample test image if none exists"""
    logger.info("Creating sample test image...")
    
    # Create a simple test image
    from PIL import ImageDraw, ImageFont
    
    img = Image.new('RGB', (1200, 800), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add some text to simulate a trading screenshot
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        font = ImageFont.load_default()
    
    # Simulate price levels
    draw.text((50, 100), "BTCUSDT", fill='black', font=font)
    draw.text((50, 150), "Entry: 65,000", fill='blue', font=font)
    draw.text((50, 200), "TP1: 66,500", fill='green', font=font)
    draw.text((50, 250), "TP2: 67,000", fill='green', font=font)
    draw.text((50, 300), "SL: 63,000", fill='red', font=font)
    
    # Add some lines to simulate a chart
    draw.line([(200, 400), (1000, 350)], fill='blue', width=2)
    draw.line([(200, 450), (1000, 450)], fill='gray', width=1)
    
    img.save("test_screenshot.png")
    logger.info("Sample test image created: test_screenshot.png")
    
    return img

if __name__ == "__main__":
    # Check if test image exists, create one if not
    import os
    if not os.path.exists("test_screenshot.png"):
        create_sample_image()
    
    # Run enhancement tests
    asyncio.run(test_enhancement())