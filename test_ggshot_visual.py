#!/usr/bin/env python3
"""
Create visual test screenshots for GGShot with colored boxes
"""
import asyncio
import sys
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

def create_long_screenshot():
    """Create a LONG trade screenshot with colored boxes"""
    # Create dark mobile screenshot
    img = Image.new('RGB', (1080, 2400), color=(20, 20, 25))
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
    
    # Header
    draw.text((50, 50), "BTCUSDT", fill=(200, 200, 210), font=font_large)
    draw.text((50, 110), "LONG Position", fill=(50, 220, 50), font=font_medium)
    
    y_start = 300
    
    # Stop Loss (grey box at bottom)
    sl_y = y_start + 600
    draw.rectangle([(900, sl_y-25), (1030, sl_y+25)], fill=(80, 80, 80), outline=(120, 120, 120))
    draw.text((920, sl_y-15), "60000", fill=(255, 255, 255), font=font_medium)
    draw.text((50, sl_y-15), "Stop Loss", fill=(180, 180, 180), font=font_medium)
    
    # Entry prices (red boxes, closer to SL)
    entries = [
        ("62000", y_start + 450),  # Primary entry (highest)
        ("61500", y_start + 500),  # Limit 1
        ("61000", y_start + 550),  # Limit 2
    ]
    
    for i, (price, y) in enumerate(entries):
        draw.rectangle([(900, y-25), (1030, y+25)], fill=(180, 40, 40), outline=(220, 60, 60))
        draw.text((920, y-15), price, fill=(255, 255, 255), font=font_medium)
        label = "Entry" if i == 0 else f"Limit {i}"
        draw.text((50, y-15), label, fill=(200, 200, 200), font=font_medium)
    
    # Take profits (red boxes, farther from SL)
    tps = [
        ("63000", y_start + 300),  # TP1 (lowest TP)
        ("64000", y_start + 200),  # TP2
        ("65000", y_start + 100),  # TP3
        ("66000", y_start),        # TP4 (highest TP)
    ]
    
    for i, (price, y) in enumerate(tps):
        draw.rectangle([(900, y-25), (1030, y+25)], fill=(180, 40, 40), outline=(220, 60, 60))
        draw.text((920, y-15), price, fill=(255, 255, 255), font=font_medium)
        draw.text((50, y-15), f"TP{i+1}", fill=(200, 200, 200), font=font_medium)
    
    # Add current price indicator
    current_y = y_start + 400
    draw.line([(50, current_y), (1030, current_y)], fill=(100, 100, 255), width=2)
    draw.text((50, current_y+10), "Current: 62100", fill=(100, 100, 255), font=font_medium)
    
    img.save("test_long_colored_boxes.png")
    logger.info("Created LONG trade screenshot: test_long_colored_boxes.png")
    return "test_long_colored_boxes.png"

def create_short_screenshot():
    """Create a SHORT trade screenshot with colored boxes"""
    # Create dark mobile screenshot
    img = Image.new('RGB', (1080, 2400), color=(20, 20, 25))
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
    
    # Header
    draw.text((50, 50), "ETHUSDT", fill=(200, 200, 210), font=font_large)
    draw.text((50, 110), "SHORT Position", fill=(220, 50, 50), font=font_medium)
    
    y_start = 300
    
    # Stop Loss (grey box at top)
    sl_y = y_start
    draw.rectangle([(900, sl_y-25), (1030, sl_y+25)], fill=(80, 80, 80), outline=(120, 120, 120))
    draw.text((920, sl_y-15), "3500", fill=(255, 255, 255), font=font_medium)
    draw.text((50, sl_y-15), "Stop Loss", fill=(180, 180, 180), font=font_medium)
    
    # Entry prices (red boxes, closer to SL)
    entries = [
        ("3400", y_start + 100),  # Primary entry (lowest)
        ("3420", y_start + 80),   # Limit 1
        ("3440", y_start + 60),   # Limit 2
    ]
    
    for i, (price, y) in enumerate(entries):
        draw.rectangle([(900, y-25), (1030, y+25)], fill=(180, 40, 40), outline=(220, 60, 60))
        draw.text((920, y-15), price, fill=(255, 255, 255), font=font_medium)
        label = "Entry" if i == 0 else f"Limit {i}"
        draw.text((50, y-15), label, fill=(200, 200, 200), font=font_medium)
    
    # Take profits (red boxes, farther from SL)
    tps = [
        ("3300", y_start + 250),  # TP1 (highest TP)
        ("3200", y_start + 350),  # TP2
        ("3100", y_start + 450),  # TP3
        ("3000", y_start + 550),  # TP4 (lowest TP)
    ]
    
    for i, (price, y) in enumerate(tps):
        draw.rectangle([(900, y-25), (1030, y+25)], fill=(180, 40, 40), outline=(220, 60, 60))
        draw.text((920, y-15), price, fill=(255, 255, 255), font=font_medium)
        draw.text((50, y-15), f"TP{i+1}", fill=(200, 200, 200), font=font_medium)
    
    # Add current price indicator
    current_y = y_start + 150
    draw.line([(50, current_y), (1030, current_y)], fill=(100, 100, 255), width=2)
    draw.text((50, current_y+10), "Current: 3395", fill=(100, 100, 255), font=font_medium)
    
    img.save("test_short_colored_boxes.png")
    logger.info("Created SHORT trade screenshot: test_short_colored_boxes.png")
    return "test_short_colored_boxes.png"

async def test_long_extraction():
    """Test LONG trade extraction"""
    logger.info("\n" + "="*60)
    logger.info("Testing LONG Trade Extraction")
    logger.info("="*60)
    
    image_path = create_long_screenshot()
    
    result = await screenshot_analyzer.analyze_trading_screenshot(
        image_path,
        "BTCUSDT",
        "Buy"
    )
    
    if result.get('success') and result.get('parameters'):
        params = result['parameters']
        logger.info("\nExtracted LONG parameters:")
        logger.info(f"Primary Entry: {params.get('primary_entry', 'N/A')}")
        logger.info(f"Limit Entry 1: {params.get('limit_entry_1_price', 'N/A')}")
        logger.info(f"Limit Entry 2: {params.get('limit_entry_2_price', 'N/A')}")
        logger.info(f"TP1: {params.get('tp1_price', 'N/A')}")
        logger.info(f"TP2: {params.get('tp2_price', 'N/A')}")
        logger.info(f"TP3: {params.get('tp3_price', 'N/A')}")
        logger.info(f"TP4: {params.get('tp4_price', 'N/A')}")
        logger.info(f"Stop Loss: {params.get('sl_price', 'N/A')}")
    else:
        logger.error(f"Extraction failed: {result.get('error', 'Unknown error')}")

async def test_short_extraction():
    """Test SHORT trade extraction"""
    logger.info("\n" + "="*60)
    logger.info("Testing SHORT Trade Extraction")
    logger.info("="*60)
    
    image_path = create_short_screenshot()
    
    result = await screenshot_analyzer.analyze_trading_screenshot(
        image_path,
        "ETHUSDT",
        "Sell"
    )
    
    if result.get('success') and result.get('parameters'):
        params = result['parameters']
        logger.info("\nExtracted SHORT parameters:")
        logger.info(f"Primary Entry: {params.get('primary_entry', 'N/A')}")
        logger.info(f"Limit Entry 1: {params.get('limit_entry_1_price', 'N/A')}")
        logger.info(f"Limit Entry 2: {params.get('limit_entry_2_price', 'N/A')}")
        logger.info(f"TP1: {params.get('tp1_price', 'N/A')}")
        logger.info(f"TP2: {params.get('tp2_price', 'N/A')}")
        logger.info(f"TP3: {params.get('tp3_price', 'N/A')}")
        logger.info(f"TP4: {params.get('tp4_price', 'N/A')}")
        logger.info(f"Stop Loss: {params.get('sl_price', 'N/A')}")
    else:
        logger.error(f"Extraction failed: {result.get('error', 'Unknown error')}")

async def main():
    """Run visual tests"""
    await test_long_extraction()
    await test_short_extraction()
    
    logger.info("\n" + "="*60)
    logger.info("Visual tests complete!")
    logger.info("Check the generated images and debug_enhanced_*.png files")
    logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(main())