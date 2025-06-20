#!/usr/bin/env python3
"""
Test GGShot accuracy improvements
"""
import asyncio
import sys
import os
from PIL import Image, ImageDraw, ImageFont
import logging

# Add parent directory to path
sys.path.append('.')

from utils.screenshot_analyzer import screenshot_analyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def create_test_screenshot():
    """Create a test screenshot similar to user's dark mobile screenshot"""
    
    # Create dark mobile screenshot with all values
    img = Image.new('RGB', (1178, 2560), color=(15, 15, 20))  # Very dark background
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Header
    draw.text((50, 50), "LDOUSDT", fill=(200, 200, 210), font=font_large)
    draw.text((50, 100), "SHORT", fill=(220, 50, 50), font=font_medium)
    
    # Draw horizontal lines for price levels
    y_positions = {
        'sl': 400,
        'e1': 500,
        'e2': 600,
        'e3': 700,
        'tp1': 900,
        'tp2': 1100,
        'tp3': 1300,
        'tp4': 1500
    }
    
    # Stop Loss (red)
    draw.line([(50, y_positions['sl']), (1128, y_positions['sl'])], fill=(180, 50, 50), width=3)
    draw.text((50, y_positions['sl'] - 30), "SL", fill=(180, 50, 50), font=font_medium)
    draw.text((1000, y_positions['sl'] - 30), "1.9500", fill=(180, 50, 50), font=font_large)
    
    # Entry levels (white/gray)
    draw.line([(50, y_positions['e1']), (1128, y_positions['e1'])], fill=(150, 150, 160), width=2)
    draw.text((50, y_positions['e1'] - 30), "Entry 1", fill=(150, 150, 160), font=font_medium)
    draw.text((1000, y_positions['e1'] - 30), "1.8950", fill=(150, 150, 160), font=font_large)
    
    draw.line([(50, y_positions['e2']), (1128, y_positions['e2'])], fill=(130, 130, 140), width=2)
    draw.text((50, y_positions['e2'] - 30), "Entry 2", fill=(130, 130, 140), font=font_medium)
    draw.text((1000, y_positions['e2'] - 30), "1.9100", fill=(130, 130, 140), font=font_large)
    
    draw.line([(50, y_positions['e3']), (1128, y_positions['e3'])], fill=(110, 110, 120), width=2)
    draw.text((50, y_positions['e3'] - 30), "Entry 3", fill=(110, 110, 120), font=font_medium)
    draw.text((1000, y_positions['e3'] - 30), "1.9250", fill=(110, 110, 120), font=font_large)
    
    # Take Profit levels (green)
    draw.line([(50, y_positions['tp1']), (1128, y_positions['tp1'])], fill=(50, 180, 50), width=3)
    draw.text((50, y_positions['tp1'] - 30), "TP1", fill=(50, 180, 50), font=font_medium)
    draw.text((1000, y_positions['tp1'] - 30), "1.8500", fill=(50, 180, 50), font=font_large)
    
    draw.line([(50, y_positions['tp2']), (1128, y_positions['tp2'])], fill=(50, 160, 50), width=2)
    draw.text((50, y_positions['tp2'] - 30), "TP2", fill=(50, 160, 50), font=font_medium)
    draw.text((1000, y_positions['tp2'] - 30), "1.8000", fill=(50, 160, 50), font=font_large)
    
    draw.line([(50, y_positions['tp3']), (1128, y_positions['tp3'])], fill=(50, 140, 50), width=2)
    draw.text((50, y_positions['tp3'] - 30), "TP3", fill=(50, 140, 50), font=font_medium)
    draw.text((1000, y_positions['tp3'] - 30), "1.7500", fill=(50, 140, 50), font=font_large)
    
    draw.line([(50, y_positions['tp4']), (1128, y_positions['tp4'])], fill=(50, 120, 50), width=2)
    draw.text((50, y_positions['tp4'] - 30), "TP4", fill=(50, 120, 50), font=font_medium)
    draw.text((1000, y_positions['tp4'] - 30), "1.7000", fill=(50, 120, 50), font=font_large)
    
    # Add some chart elements
    draw.line([(100, 1700), (1078, 1750)], fill=(60, 60, 70), width=2)
    draw.line([(100, 1800), (1078, 1780)], fill=(40, 40, 50), width=1)
    
    # Save test image
    img.save("test_ggshot_mobile_dark.png")
    logger.info("Created test screenshot: test_ggshot_mobile_dark.png")
    
    return "test_ggshot_mobile_dark.png"

async def test_extraction():
    """Test the extraction with the dark mobile screenshot"""
    
    # Create test screenshot
    image_path = await create_test_screenshot()
    
    logger.info("\n" + "="*60)
    logger.info("Testing GGShot extraction accuracy...")
    logger.info("="*60)
    
    # Test extraction
    result = await screenshot_analyzer.analyze_trading_screenshot(
        image_path,
        "LDOUSDT",
        "Sell"
    )
    
    # Print results
    logger.info(f"\nExtraction success: {result.get('success')}")
    logger.info(f"Confidence: {result.get('confidence', 0)}")
    logger.info(f"Strategy type: {result.get('strategy_type')}")
    logger.info(f"Extraction method: {result.get('extraction_method', 'unknown')}")
    
    if result.get('success') and result.get('parameters'):
        params = result['parameters']
        logger.info("\n📊 EXTRACTED PARAMETERS:")
        logger.info("="*40)
        
        # Expected values
        expected = {
            'primary_entry': '1.8950',
            'limit_entry_1': '1.9100',
            'limit_entry_2': '1.9250',
            'limit_entry_3': None,  # We didn't add a 4th entry
            'tp1_price': '1.8500',
            'tp2_price': '1.8000',
            'tp3_price': '1.7500',
            'tp4_price': '1.7000',
            'sl_price': '1.9500'
        }
        
        # Compare extracted vs expected
        for key, expected_val in expected.items():
            extracted_val = params.get(key, 'N/A')
            if key in params and params[key] is not None:
                extracted_str = str(params[key])
                match = "✅" if extracted_str == expected_val else "❌"
            else:
                extracted_str = "N/A"
                match = "❌" if expected_val is not None else "➖"
            
            logger.info(f"{key:20} Expected: {expected_val or 'N/A':10} Got: {extracted_str:10} {match}")
    
    # Check notes
    if result.get('notes'):
        logger.info(f"\nNotes: {result['notes']}")
    
    # Check validation errors
    if result.get('validation_errors'):
        logger.info(f"\nValidation errors: {result['validation_errors']}")
    
    logger.info("\n" + "="*60)
    logger.info("Check the debug_enhanced_*.png files to see what the AI analyzed")
    logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(test_extraction())