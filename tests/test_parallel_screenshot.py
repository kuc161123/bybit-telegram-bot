#!/usr/bin/env python3
"""
Test parallel screenshot analysis
"""
import asyncio
import logging
from utils.screenshot_analyzer import ScreenshotAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_parallel_analysis():
    """Test the parallel model analysis"""
    analyzer = ScreenshotAnalyzer()
    
    # Use a test image path (you'll need to provide an actual screenshot)
    test_image = "test_screenshot.png"  # Replace with actual path
    symbol = "BTCUSDT"
    side = "Buy"
    
    print("\n🚀 Testing Parallel Screenshot Analysis\n")
    print("This will run multiple strategies simultaneously:")
    print("  • GPT-4o-mini (simple) - fastest")
    print("  • GPT-4o-mini (numbers) - focused extraction")
    print("  • GPT-4o (detailed) - most accurate")
    print("\nStarting analysis...\n")
    
    try:
        # Analyze screenshot
        result = await analyzer.analyze_trading_screenshot(test_image, symbol, side)
        
        if result.get("success"):
            print("\n✅ Analysis Successful!\n")
            
            # Show parallel analysis results
            if "parallel_analysis" in result:
                pa = result["parallel_analysis"]
                print(f"Models tried: {pa['models_tried']}")
                print(f"Models succeeded: {pa['models_succeeded']}")
                print(f"Best model: {pa['best_model']}\n")
                
                print("All model results:")
                for model, confidence in pa['all_results']:
                    print(f"  - {model}: confidence={confidence:.2f}")
            
            # Show extracted parameters
            print(f"\nStrategy: {result.get('strategy_type', 'unknown')}")
            print(f"Confidence: {result.get('composite_confidence', 0):.2f}")
            
            params = result.get("parameters", {})
            print("\nExtracted parameters:")
            for key, value in params.items():
                print(f"  {key}: {value}")
        else:
            print(f"\n❌ Analysis failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n💥 Error: {e}")

if __name__ == "__main__":
    print("Note: You need to provide a valid screenshot path in the script")
    print("Example: test_image = '/path/to/your/screenshot.png'")
    # asyncio.run(test_parallel_analysis())