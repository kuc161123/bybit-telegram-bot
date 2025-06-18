#!/usr/bin/env python3
"""
Screenshot analysis using OpenAI Vision API for GGShot trading strategy.
Extracts trading parameters from TradingView screenshots with OCR analysis.
"""
import asyncio
import logging
import base64
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageEnhance
import requests
from html import escape

from config.settings import OPENAI_API_KEY, LLM_PROVIDER
from config.constants import *
from clients.ai_client import openai_client

logger = logging.getLogger(__name__)

class ScreenshotAnalyzer:
    """Analyzes trading screenshots using OpenAI Vision API"""
    
    def __init__(self):
        self.client = openai_client
        self.max_image_size = (1024, 1024)  # Reduce size for API efficiency
        
    async def analyze_trading_screenshot(self, image_url: str, symbol: str, side: str) -> Dict[str, Any]:
        """
        Analyze trading screenshot and extract parameters
        
        Args:
            image_url: URL or file path to the screenshot
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: Trade direction ("Buy" or "Sell")
            
        Returns:
            Dict containing analysis results and extracted parameters
        """
        try:
            if not self.client or LLM_PROVIDER != "openai":
                logger.warning("OpenAI client not available, falling back to mock analysis")
                return await self._mock_analysis(symbol, side)
            
            # Download and preprocess image
            processed_image = await self._download_and_preprocess_image(image_url)
            if not processed_image:
                return self._error_result("Failed to download or process image")
            
            # Convert image to base64
            base64_image = self._image_to_base64(processed_image)
            if not base64_image:
                return self._error_result("Failed to convert image to base64")
            
            # Analyze with OpenAI Vision API
            analysis_result = await self._analyze_with_openai(base64_image, symbol, side)
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in screenshot analysis: {e}")
            return self._error_result(f"Analysis failed: {str(e)}")
    
    async def _download_and_preprocess_image(self, image_url: str) -> Optional[Image.Image]:
        """Download and preprocess image for better OCR results"""
        try:
            # Download image
            if image_url.startswith('http'):
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
                image_data = response.content
            else:
                # Assume it's a file path
                with open(image_url, 'rb') as f:
                    image_data = f.read()
            
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance image for better OCR
            image = self._enhance_image_for_ocr(image)
            
            # Resize if too large
            if image.size[0] > self.max_image_size[0] or image.size[1] > self.max_image_size[1]:
                image.thumbnail(self.max_image_size, Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            logger.error(f"Error downloading/preprocessing image: {e}")
            return None
    
    def _enhance_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Enhance image contrast and sharpness for better OCR results"""
        try:
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            return image
            
        except Exception as e:
            logger.error(f"Error enhancing image: {e}")
            return image
    
    def _image_to_base64(self, image: Image.Image) -> Optional[str]:
        """Convert PIL Image to base64 string"""
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)
            
            image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            return image_base64
            
        except Exception as e:
            logger.error(f"Error converting image to base64: {e}")
            return None
    
    async def _analyze_with_openai(self, base64_image: str, symbol: str, side: str) -> Dict[str, Any]:
        """Analyze image using OpenAI Vision API"""
        try:
            # Create system prompt for trading parameter extraction
            system_prompt = self._create_analysis_prompt(symbol, side)
            
            # Call OpenAI Vision API
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4o",  # GPT-4 with vision capabilities
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Analyze this TradingView screenshot for {symbol} {side} trade and extract the trading parameters in the specified JSON format."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent extraction
            )
            
            # Parse response
            content = response.choices[0].message.content
            return await self._parse_openai_response(content, symbol, side)
            
        except Exception as e:
            logger.error(f"Error calling OpenAI Vision API: {e}")
            return self._error_result(f"OpenAI API error: {str(e)}")
    
    def _create_analysis_prompt(self, symbol: str, side: str) -> str:
        """Create detailed analysis prompt for OpenAI Vision API"""
        direction = "LONG" if side == "Buy" else "SHORT"
        
        return f"""You are an expert trading analyst specialized in extracting parameters from TradingView screenshots.

TASK: Analyze the screenshot and extract trading parameters for a {direction} position on {symbol}.

Look for the following elements in the image:
1. Entry prices (market price, limit order levels)
2. Take profit levels (TP1, TP2, TP3, TP4)
3. Stop loss level
4. Any visible leverage or margin information
5. GGShot indicator signals or levels
6. Support/resistance levels
7. Price annotations or labels

STRATEGY DETECTION:
- If multiple entry levels or take profits are visible → "conservative" strategy
- If single entry/exit levels are visible → "fast" strategy

OUTPUT FORMAT (JSON only, no other text):
{{
    "success": true/false,
    "confidence": 0.0-1.0,
    "strategy_type": "conservative" or "fast",
    "parameters": {{
        "primary_entry": decimal_price,
        "limit_entry_1": decimal_price (if conservative),
        "limit_entry_2": decimal_price (if conservative),
        "limit_entry_3": decimal_price (if conservative),
        "tp1_price": decimal_price,
        "tp2_price": decimal_price (if conservative),
        "tp3_price": decimal_price (if conservative),
        "tp4_price": decimal_price (if conservative),
        "sl_price": decimal_price,
        "leverage": integer (default 10 if not visible),
        "margin_amount": decimal (default 100 if not visible)
    }},
    "notes": "Brief explanation of what was detected"
}}

IMPORTANT:
- Extract actual numeric values from the image
- If price levels are not clearly visible, set success to false
- Confidence should reflect how clearly the levels were visible
- For {direction} trades, ensure TP > entry and SL < entry (for LONG), opposite for SHORT
- Use conservative strategy if 3+ entry levels or 4 TP levels are detected"""

    async def _parse_openai_response(self, content: str, symbol: str, side: str) -> Dict[str, Any]:
        """Parse OpenAI response and convert to internal format"""
        try:
            import json
            
            # Try to extract JSON from response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            # Parse JSON response
            result = json.loads(content)
            
            if not result.get("success"):
                return self._error_result(result.get("notes", "Analysis failed"))
            
            # Convert parameters to internal format
            params = result.get("parameters", {})
            strategy_type = result.get("strategy_type", "fast")
            
            # Map to internal constants
            internal_params = {}
            
            # Entry prices
            if "primary_entry" in params:
                internal_params[PRIMARY_ENTRY_PRICE] = Decimal(str(params["primary_entry"]))
            
            if strategy_type == "conservative":
                if "limit_entry_1" in params:
                    internal_params[LIMIT_ENTRY_1_PRICE] = Decimal(str(params["limit_entry_1"]))
                if "limit_entry_2" in params:
                    internal_params[LIMIT_ENTRY_2_PRICE] = Decimal(str(params["limit_entry_2"]))
                if "limit_entry_3" in params:
                    internal_params[LIMIT_ENTRY_3_PRICE] = Decimal(str(params["limit_entry_3"]))
            
            # Take profits
            if "tp1_price" in params:
                internal_params[TP1_PRICE] = Decimal(str(params["tp1_price"]))
            if "tp2_price" in params and strategy_type == "conservative":
                internal_params[TP2_PRICE] = Decimal(str(params["tp2_price"]))
            if "tp3_price" in params and strategy_type == "conservative":
                internal_params[TP3_PRICE] = Decimal(str(params["tp3_price"]))
            if "tp4_price" in params and strategy_type == "conservative":
                internal_params[TP4_PRICE] = Decimal(str(params["tp4_price"]))
            
            # Stop loss
            if "sl_price" in params:
                internal_params[SL_PRICE] = Decimal(str(params["sl_price"]))
            
            # Leverage and margin
            internal_params["leverage"] = int(params.get("leverage", 10))
            internal_params["margin_amount"] = Decimal(str(params.get("margin_amount", 100)))
            
            # ENHANCED: Validate extracted parameters
            from utils.ggshot_validator import validate_ggshot_parameters
            try:
                # Get current market price if possible
                from utils.cache import get_ticker_price_cached
                current_price = await get_ticker_price_cached(symbol)
            except:
                current_price = None
            
            # Validate parameters
            success, errors, validated_params = await validate_ggshot_parameters(
                internal_params, symbol, side, current_price
            )
            
            if not success:
                logger.warning(f"Parameter validation failed: {errors}")
                return {
                    "success": False,
                    "confidence": result.get("confidence", 0.0),
                    "strategy_type": strategy_type,
                    "parameters": internal_params,
                    "validation_errors": errors,
                    "notes": "AI extraction successful but validation failed"
                }
            
            return {
                "success": True,
                "confidence": result.get("confidence", 0.8),
                "strategy_type": strategy_type,
                "parameters": validated_params,  # Use validated/corrected params
                "notes": result.get("notes", "Analysis completed successfully")
            }
            
        except (json.JSONDecodeError, ValueError, InvalidOperation) as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            # Escape HTML special characters in error message
            error_msg = escape(str(e))
            return self._error_result(f"Failed to parse analysis result: {error_msg}")
    
    async def _mock_analysis(self, symbol: str, side: str) -> Dict[str, Any]:
        """Fallback mock analysis when OpenAI is not available"""
        logger.info("Using mock analysis - OpenAI not configured")
        
        # Simulate processing delay
        await asyncio.sleep(2)
        
        if side == "Buy":
            return {
                "success": True,
                "confidence": 0.85,
                "strategy_type": "conservative",
                "parameters": {
                    PRIMARY_ENTRY_PRICE: Decimal("65000"),
                    LIMIT_ENTRY_1_PRICE: Decimal("64800"),
                    LIMIT_ENTRY_2_PRICE: Decimal("64600"),
                    LIMIT_ENTRY_3_PRICE: Decimal("64400"),
                    TP1_PRICE: Decimal("66500"),
                    TP2_PRICE: Decimal("67000"),
                    TP3_PRICE: Decimal("67500"),
                    TP4_PRICE: Decimal("68000"),
                    SL_PRICE: Decimal("63000"),
                    "leverage": 10,
                    "margin_amount": Decimal("100")
                },
                "notes": "Mock analysis - configure OpenAI for real extraction"
            }
        else:
            return {
                "success": True,
                "confidence": 0.80,
                "strategy_type": "fast",
                "parameters": {
                    PRIMARY_ENTRY_PRICE: Decimal("65000"),
                    TP1_PRICE: Decimal("64000"),
                    SL_PRICE: Decimal("66000"),
                    "leverage": 10,
                    "margin_amount": Decimal("100")
                },
                "notes": "Mock analysis - configure OpenAI for real extraction"
            }
    
    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Create standardized error result"""
        # Ensure error message is HTML-safe
        return {
            "success": False,
            "confidence": 0.0,
            "error": escape(error_message),
            "parameters": {}
        }

# Global analyzer instance
screenshot_analyzer = ScreenshotAnalyzer()

async def analyze_trading_screenshot(image_url: str, symbol: str, side: str) -> Dict[str, Any]:
    """
    Convenience function to analyze trading screenshot
    
    Args:
        image_url: URL or file path to the screenshot
        symbol: Trading symbol (e.g., "BTCUSDT")
        side: Trade direction ("Buy" or "Sell")
        
    Returns:
        Dict containing analysis results and extracted parameters
    """
    return await screenshot_analyzer.analyze_trading_screenshot(image_url, symbol, side)