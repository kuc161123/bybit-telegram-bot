#!/usr/bin/env python3
"""
Test color box extraction specifically
"""
import asyncio
import logging
import sys
from PIL import Image, ImageDraw, ImageFont
import json

# Add parent directory to path
sys.path.append('.')

from utils.screenshot_analyzer import screenshot_analyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_screenshot_with_colored_boxes():
    """Create test screenshot with actual colored boxes like the user described"""
    # Create dark mobile screenshot
    img = Image.new('RGB', (1080, 2400), color=(15, 15, 20))
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
    
    # Header
    draw.text((50, 50), "LDOUSDT", fill=(200, 200, 210), font=font_large)
    draw.text((50, 120), "SHORT", fill=(220, 50, 50), font=font_medium)
    
    y_start = 300
    
    # Based on user's description:
    # - Stop loss has GREY box
    # - Entries and TPs have RED boxes
    
    # Stop Loss with GREY box (at top for SHORT)
    sl_y = y_start
    # Draw grey box background
    draw.rectangle([(850, sl_y-30), (1030, sl_y+30)], fill=(80, 80, 80))
    draw.text((870, sl_y-20), "1.9500", fill=(255, 255, 255), font=font_large)
    draw.text((50, sl_y-15), "Stop Loss", fill=(180, 180, 180), font=font_medium)
    
    # Entry prices with RED boxes (for SHORT: lowest to highest)
    entries = [
        ("1.8950", y_start + 150),  # Primary entry (lowest/closest to current)
        ("1.9100", y_start + 100),  # Limit 1 (higher)
        ("1.9250", y_start + 50),   # Limit 2 (highest)
    ]
    
    for i, (price, y) in enumerate(entries):
        # Draw red box background
        draw.rectangle([(850, y-30), (1030, y+30)], fill=(180, 40, 40))
        draw.text((870, y-20), price, fill=(255, 255, 255), font=font_large)
        label = "Entry" if i == 0 else f"Limit {i}"
        draw.text((50, y-15), label, fill=(200, 200, 200), font=font_medium)
    
    # Take profits with RED boxes (for SHORT: highest to lowest)
    tps = [
        ("1.8500", y_start + 300),  # TP1 (highest)
        ("1.8000", y_start + 400),  # TP2
        ("1.7500", y_start + 500),  # TP3
        ("1.7000", y_start + 600),  # TP4 (lowest)
    ]
    
    for i, (price, y) in enumerate(tps):
        # Draw red box background
        draw.rectangle([(850, y-30), (1030, y+30)], fill=(180, 40, 40))
        draw.text((870, y-20), price, fill=(255, 255, 255), font=font_large)
        draw.text((50, y-15), f"TP{i+1}", fill=(200, 200, 200), font=font_medium)
    
    # Current price line
    current_y = y_start + 200
    draw.line([(50, current_y), (1030, current_y)], fill=(100, 100, 255), width=2)
    draw.text((50, current_y+10), "Current: 1.8900", fill=(100, 100, 255), font=font_medium)
    
    img.save("test_colored_boxes_short.png")
    logger.info("Created test screenshot with colored boxes: test_colored_boxes_short.png")
    return "test_colored_boxes_short.png"

async def test_color_extraction():
    """Test extraction with colored boxes"""
    logger.info("\n" + "="*60)
    logger.info("Testing Color Box Extraction")
    logger.info("="*60)
    
    image_path = create_test_screenshot_with_colored_boxes()
    
    # Expected values for SHORT trade
    expected = {
        'primary_entry': '1.8950',  # Lowest (closest to current)
        'limit_entry_1': '1.9100',  # Higher
        'limit_entry_2': '1.9250',  # Highest
        'tp1_price': '1.8500',      # Highest TP
        'tp2_price': '1.8000',
        'tp3_price': '1.7500',
        'tp4_price': '1.7000',      # Lowest TP
        'sl_price': '1.9500'        # Stop loss in grey box
    }
    
    logger.info("\nExpected values for SHORT trade:")
    logger.info(f"Stop Loss (grey box): {expected['sl_price']}")
    logger.info(f"Primary Entry (red box, lowest): {expected['primary_entry']}")
    logger.info(f"Limit 1 (red box): {expected['limit_entry_1']}")
    logger.info(f"Limit 2 (red box): {expected['limit_entry_2']}")
    logger.info(f"TP1 (red box, highest TP): {expected['tp1_price']}")
    logger.info(f"TP2 (red box): {expected['tp2_price']}")
    logger.info(f"TP3 (red box): {expected['tp3_price']}")
    logger.info(f"TP4 (red box, lowest TP): {expected['tp4_price']}")
    
    # Test extraction
    result = await screenshot_analyzer.analyze_trading_screenshot(
        image_path,
        "LDOUSDT",
        "Sell"
    )
    
    logger.info(f"\nExtraction result: {'SUCCESS' if result.get('success') else 'FAILED'}")
    logger.info(f"Confidence: {result.get('confidence', 0)}")
    logger.info(f"Strategy: {result.get('strategy_type')}")
    logger.info(f"Method: {result.get('extraction_method', 'unknown')}")
    
    if result.get('success') and result.get('parameters'):
        params = result['parameters']
        logger.info("\n📊 EXTRACTED vs EXPECTED:")
        logger.info("="*50)
        
        for key, expected_val in expected.items():
            extracted_val = params.get(key, 'N/A')
            if key in params and params[key] is not None:
                extracted_str = str(params[key])
                match = "✅" if extracted_str == expected_val else "❌"
            else:
                extracted_str = "N/A"
                match = "❌"
            
            logger.info(f"{key:20} Expected: {expected_val:10} Got: {extracted_str:10} {match}")
    
    if result.get('notes'):
        logger.info(f"\nNotes: {result['notes']}")
    
    if result.get('validation_errors'):
        logger.info(f"\nValidation errors: {', '.join(result['validation_errors'])}")

async def analyze_user_screenshot():
    """Analyze what the user's actual screenshot might contain"""
    logger.info("\n" + "="*60)
    logger.info("Analyzing User's Screenshot Pattern")
    logger.info("="*60)
    
    logger.info("\nBased on extraction attempts, the system found these values:")
    logger.info("Pass 1: 0.9000, 0.8500, 0.8000, 0.7500, 0.7000, 0.6500, 0.6000, 0.5000")
    logger.info("Pass 2: 0.9000, 0.8500, 0.8000, 0.7500, 0.7000, 0.6500, 0.6000, 0.5500, 0.5000")
    logger.info("Emergency: 0.9000, 0.8500, 0.8000, 0.7500, 0.7000, 0.6500, 0.6000, 0.5500, 0.5000, 0.4500")
    
    logger.info("\nThe issue appears to be:")
    logger.info("1. The system is finding the numbers but not identifying which are in RED vs GREY boxes")
    logger.info("2. For SHORT trades, the entry order should be:")
    logger.info("   - Primary Entry: LOWEST value in red box closest to current price")
    logger.info("   - Limit 1: Next higher value in red box")
    logger.info("   - Limit 2: Highest value in red box")
    logger.info("3. The stop loss should be the value in the GREY box")
    
    logger.info("\nTo fix this, we need to ensure the OCR specifically identifies:")
    logger.info("- Which numbers are inside RED boxes")
    logger.info("- Which number is inside the GREY box")
    logger.info("- The relative positions to determine entry vs TP")

async def main():
    """Run tests"""
    await test_color_extraction()
    await analyze_user_screenshot()
    
    logger.info("\n" + "="*60)
    logger.info("Color Box Extraction Test Complete")
    logger.info("="*60)
    logger.info("\nThe system needs to:")
    logger.info("1. Detect the COLOR of the box around each number")
    logger.info("2. Use color to identify price type (grey=SL, red=entry/TP)")
    logger.info("3. Use position relative to SL to determine entry vs TP")
    logger.info("4. Order entries correctly for trade direction")

if __name__ == "__main__":
    asyncio.run(main())