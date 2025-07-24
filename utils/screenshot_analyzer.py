#!/usr/bin/env python3
"""
Screenshot analysis using OpenAI Vision API for GGShot trading strategy.
Extracts trading parameters from TradingView screenshots with OCR analysis.
"""
import asyncio
import logging
import base64
import io
import numpy as np
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import requests
from html import escape

from config.settings import OPENAI_API_KEY, LLM_PROVIDER
from config.constants import *
from clients.ai_client import openai_client
from utils.image_enhancer import enhance_screenshot, enhance_tradingview

logger = logging.getLogger(__name__)

class ScreenshotAnalyzer:
    """Analyzes trading screenshots using OpenAI Vision API"""

    def __init__(self):
        self.client = openai_client
        self.max_image_size = (1024, 1024)  # Reduce size for API efficiency
        self.enhancement_level = "standard"  # Can be "quick", "standard", or "advanced"
        self.debug_mode = True  # Save enhanced images for debugging

    async def _parallel_model_analysis(self, base64_image: str, symbol: str, side: str, prompt_strategy: str = "simple") -> Dict[str, Any]:
        """Run multiple models in parallel and take the best result"""
        logger.info("🚀 Starting parallel model analysis for maximum speed...")

        # Define model configurations (only vision-capable models)
        models = [
            ("gpt-4o-mini", "simple"),     # Fastest, good accuracy
            ("gpt-4o-mini", "numbers_only"), # Same model, different strategy
            ("gpt-4o", "detailed")         # Slowest but most accurate
        ]

        # Create tasks for parallel execution
        tasks = []
        for model, strategy in models:
            task = asyncio.create_task(
                self._analyze_with_openai(base64_image, symbol, side, strategy, model)
            )
            tasks.append((model, strategy, task))

        # Wait for all tasks to complete
        results = []
        for model, strategy, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=15.0)  # 15 second timeout per model
                if result.get("success"):
                    # Calculate confidence for this result
                    confidence = await self._calculate_extraction_confidence(result, symbol, side)
                    result["composite_confidence"] = confidence
                    result["prompt_strategy"] = strategy
                    results.append((model, strategy, result, confidence))
                    logger.info(f"✅ {model} ({strategy}) completed with confidence: {confidence:.2f}")
                else:
                    logger.warning(f"❌ {model} ({strategy}) failed: {result.get('error', 'Unknown error')}")
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ {model} ({strategy}) timed out")
            except Exception as e:
                logger.error(f"💥 {model} ({strategy}) error: {e}")

        if not results:
            return self._error_result("All models failed to extract parameters")

        # Sort by confidence and take the best
        results.sort(key=lambda x: x[3], reverse=True)
        best_model, best_strategy, best_result, best_confidence = results[0]

        # Log all results for comparison
        logger.info("📊 Parallel model results:")
        for model, strategy, result, confidence in results:
            logger.info(f"  - {model} ({strategy}): confidence={confidence:.2f}, strategy_type={result.get('strategy_type', 'unknown')}")

        logger.info(f"🏆 Selected {best_model} ({best_strategy}) with confidence {best_confidence:.2f}")

        # Add parallel analysis metadata
        best_result["parallel_analysis"] = {
            "models_tried": len(models),
            "models_succeeded": len(results),
            "all_results": [(f"{m} ({s})", c) for m, s, _, c in results],
            "best_model": f"{best_model} ({best_strategy})"
        }

        return best_result

    async def analyze_trading_screenshot(self, image_url: str, symbol: str, side: str) -> Dict[str, Any]:
        """
        Analyze trading screenshot and extract parameters with multi-pass extraction

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

            # Store original image for potential re-processing
            original_image = processed_image.copy()

            # Get quality report
            from utils.image_enhancer import image_enhancer
            _, quality_report = image_enhancer.enhance_for_ocr(processed_image, "quick")

            # Apply standard enhancement for parallel processing
            enhanced_image, _ = image_enhancer.enhance_for_ocr(processed_image.copy(), "standard")

            # Save debug image if enabled
            if self.debug_mode:
                debug_filename = f"debug_enhanced_parallel_{symbol}_{side}.png"
                try:
                    enhanced_image.save(debug_filename)
                    logger.info(f"Debug: Saved enhanced image to {debug_filename}")
                except Exception as e:
                    logger.error(f"Failed to save debug image: {e}")

            # Convert to base64
            base64_image = self._image_to_base64(enhanced_image)
            if not base64_image:
                return self._error_result("Failed to convert image to base64")

            # Use parallel model analysis for maximum speed
            parallel_result = await self._parallel_model_analysis(base64_image, symbol, side)

            if parallel_result.get("success"):
                parallel_result["quality_report"] = quality_report
                parallel_result["extraction_method"] = "parallel_model_analysis"

                # Log the winning model
                if "parallel_analysis" in parallel_result:
                    logger.info(f"🏆 Parallel analysis winner: {parallel_result['parallel_analysis']['best_model']}")

                return parallel_result
            else:
                # Final fallback - try to get ANY numbers from the image
                logger.warning("All extraction attempts failed, trying emergency number extraction")

                # Use the most enhanced version
                final_enhanced = await self._aggressive_enhance_for_ocr(original_image.copy())
                base64_image = self._image_to_base64(final_enhanced)

                if base64_image:
                    emergency_result = await self._emergency_number_extraction(base64_image, symbol, side)
                    if emergency_result.get("success"):
                        emergency_result["quality_report"] = quality_report
                        emergency_result["extraction_method"] = "emergency extraction"
                        logger.info("Emergency extraction succeeded")
                        return emergency_result

                return self._error_result("Failed to extract parameters after all attempts")

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
        """Enhance image using advanced enhancement pipeline"""
        try:
            # Use the new image enhancer
            enhanced_image, quality_report = enhance_screenshot(image, self.enhancement_level)

            # Log quality report for debugging
            logger.info(f"Image quality report: {quality_report}")

            # If it's detected as a TradingView screenshot, apply special enhancement
            if self._is_tradingview_screenshot(image):
                logger.info("Detected TradingView screenshot, applying specialized enhancement")
                enhanced_image = enhance_tradingview(enhanced_image)

            # Warn about quality issues
            if quality_report.get("is_blurry"):
                logger.warning("Image appears to be blurry, OCR accuracy may be reduced")
            if quality_report.get("is_low_res"):
                logger.warning("Image resolution is below recommended minimum")
            if quality_report["brightness"].get("has_low_contrast"):
                logger.warning("Image has low contrast, enhancement applied")

            return enhanced_image

        except Exception as e:
            logger.error(f"Error enhancing image: {e}")
            # Fallback to basic enhancement
            try:
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(1.1)
            except:
                pass
            return image

    def _is_tradingview_screenshot(self, image: Image.Image) -> bool:
        """Detect if image is likely a TradingView screenshot"""
        # Simple heuristic: check aspect ratio and size
        width, height = image.size
        aspect_ratio = width / height

        # TradingView screenshots typically have certain aspect ratios
        # and are usually wider than they are tall
        is_landscape = aspect_ratio > 1.2
        is_reasonable_size = width > 800 and height > 400

        return is_landscape and is_reasonable_size

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

    def _get_max_tokens_for_strategy(self, prompt_strategy: str) -> int:
        """Get optimal max_tokens based on prompt strategy for enhanced accuracy"""
        if prompt_strategy == "detailed":
            # Maximum tokens for comprehensive analysis with reasoning
            return 4096
        elif prompt_strategy == "simple":
            # Moderate tokens for focused extraction
            return 2000
        elif prompt_strategy == "numbers_only":
            # Lower tokens for quick number extraction
            return 1500
        else:
            # Default fallback
            return 1000

    async def _analyze_with_openai(self, base64_image: str, symbol: str, side: str, prompt_strategy: str = "detailed", model: str = "gpt-4o") -> Dict[str, Any]:
        """Analyze image using OpenAI Vision API with different prompt strategies"""
        try:
            # Create system prompt based on strategy
            if prompt_strategy == "simple":
                system_prompt = self._create_simple_analysis_prompt(symbol, side)
            elif prompt_strategy == "numbers_only":
                system_prompt = self._create_numbers_only_prompt()
            else:  # detailed (default)
                system_prompt = self._create_analysis_prompt(symbol, side)

            # Adjust user message based on prompt strategy
            if prompt_strategy == "numbers_only":
                user_message = "Extract all visible numbers from this trading screenshot."
            elif prompt_strategy == "simple":
                user_message = f"Extract price levels from this {symbol} {side} trade screenshot."
            else:
                user_message = f"Analyze this TradingView screenshot for {symbol} {side} trade and extract the trading parameters in the specified JSON format."

            # Call OpenAI Vision API
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=model,  # Use specified model
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
                                "text": user_message
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "auto" if model != "gpt-4o" else "high"  # Lower detail for faster models
                                }
                            }
                        ]
                    }
                ],
                max_tokens=self._get_max_tokens_for_strategy(prompt_strategy) if model == "gpt-4o" else min(1500, self._get_max_tokens_for_strategy(prompt_strategy)),
                temperature=0.1  # Low temperature for consistent extraction
            )

            # Parse response
            content = response.choices[0].message.content

            # Add model info to result
            result = None
            if prompt_strategy == "numbers_only":
                result = await self._parse_numbers_only_response(content, symbol, side)
            else:
                result = await self._parse_openai_response(content, symbol, side)

            if result and isinstance(result, dict):
                result["model_used"] = model

            return result

        except Exception as e:
            logger.error(f"Error calling OpenAI Vision API with model {model}: {e}")
            return self._error_result(f"OpenAI API error ({model}): {str(e)}")

    def _create_analysis_prompt(self, symbol: str, side: str) -> str:
        """Create detailed analysis prompt for OpenAI Vision API with enhanced reasoning"""
        direction = "LONG" if side == "Buy" else "SHORT"

        # Different box colors for LONG vs SHORT
        if side == "Buy":  # LONG
            boxes_description = """
CRITICAL VISUAL INDICATORS FOR LONG TRADES:
🟩 GREEN BOXES = Entry prices and Take Profit levels
- Look for numbers inside GREEN rectangular boxes
- These GREEN boxes contain ENTRY prices and TP prices
- Multiple green boxes = multiple entries or TPs

⬜ GREY BOXES = Stop Loss
- Look for numbers inside GREY/GRAY rectangular boxes
- GREY boxes contain the STOP LOSS price
- Usually only one grey box per trade"""
        else:  # SHORT
            boxes_description = """
CRITICAL VISUAL INDICATORS FOR SHORT TRADES:
🔴 RED BOXES = Entry prices and Take Profit levels
- Look for numbers inside RED rectangular boxes
- These RED boxes contain ENTRY prices and TP prices
- Multiple red boxes = multiple entries or TPs

⬜ GREY BOXES = Stop Loss
- Look for numbers inside GREY/GRAY rectangular boxes
- GREY boxes contain the STOP LOSS price
- Usually only one grey box per trade"""

        return f"""You are an expert trading analyst specialized in extracting parameters from TradingView mobile screenshots.

TASK: Analyze this mobile trading screenshot and extract ALL visible trading parameters for a {direction} position on {symbol}.

ANALYSIS APPROACH:
1. First, describe in detail what you see in the screenshot (colors, boxes, text labels, price levels)
2. Identify all colored boxes ({('green' if side == 'Buy' else 'red')}, grey) and their associated numbers
3. Look for text labels that indicate entry points, take profits, and stop loss
4. Explain your reasoning for each price identification
5. List any ambiguities or uncertainties you encounter
6. Then provide the final JSON output

{boxes_description}

📝 IMPORTANT LABELS TO IDENTIFY:
- ENTRIES: Look for {"'add long'" if side == "Buy" else "'add short'"} text labels next to prices
- TAKE PROFITS: Look for "GGshot: Take Profit" labels next to prices
- STOP LOSS: Look for "GGshot: Trailing Stop Loss" label next to price

USE THESE LABELS AS PRIMARY IDENTIFICATION METHOD!

POSITION RULES FOR {direction}:
{f"- Stop Loss (grey box): at the BOTTOM (lowest price)" if side == "Buy" else "- Stop Loss (grey box): at the TOP (highest price)"}
{f"- Entries (green boxes): ABOVE stop loss, closest to current price" if side == "Buy" else "- Entries (red boxes): BELOW stop loss, closest to current price"}
{f"- Take Profits (green boxes): ABOVE entries, farther from current price" if side == "Buy" else "- Take Profits (red boxes): BELOW entries, farther from current price"}

MOBILE SCREENSHOT TIPS:
- LOOK FOR TEXT LABELS FIRST:
  * {"'add long' = ENTRY PRICES" if side == "Buy" else "'add short' = ENTRY PRICES"}
  * "GGshot: Take Profit" = TAKE PROFIT PRICES
  * "GGshot: Trailing Stop Loss" = STOP LOSS PRICE
- The colored boxes confirm the price types:
  * {f"GREEN box = Entry or TP" if side == "Buy" else "RED box = Entry or TP"}
  * GREY box = Stop Loss
- For {direction} positions:
  * {"Entries are LOWER (green boxes below current price)" if side == "Buy" else "Entries are HIGHER (red boxes above current price)"}
  * {"TPs are HIGHER (green boxes above entries)" if side == "Buy" else "TPs are LOWER (red boxes below entries)"}
  * {"SL is LOWEST (grey box at bottom)" if side == "Buy" else "SL is HIGHEST (grey box at top)"}
- Check both left and right sides for these colored boxes
- Numbers may be small - focus on the colored boxes first

WHAT TO EXTRACT:
1. ALL entry price levels (primary + up to 3 limit entries)
2. ALL take profit levels (TP1, TP2, TP3, TP4)
3. Stop loss level
4. Any leverage or position size info

STRATEGY DETECTION:
- If you see 3+ entry levels OR 4 TP levels → "conservative" strategy
- If only 1 entry and 1 TP → "fast" strategy

OUTPUT FORMAT (JSON only):
{{
    "success": true/false,
    "confidence": 0.0-1.0,
    "strategy_type": "conservative" or "fast",
    "parameters": {{
        "primary_entry": "exact_price_as_shown",
        "limit_entry_1": "exact_price_as_shown" (if visible),
        "limit_entry_2": "exact_price_as_shown" (if visible),
        "limit_entry_3": "exact_price_as_shown" (if visible),
        "tp1_price": "exact_price_as_shown",
        "tp2_price": "exact_price_as_shown" (if visible),
        "tp3_price": "exact_price_as_shown" (if visible),
        "tp4_price": "exact_price_as_shown" (if visible),
        "sl_price": "exact_price_as_shown",
        "leverage": 10 (default if not visible),
        "margin_amount": "100" (default if not visible)
    }},
    "notes": "List ALL price numbers you can see, even if unsure of their purpose",
    "reasoning": "Explain your identification process for each price level",
    "visible_elements": "Describe all colored boxes, labels, and numbers you can see"
}}

CRITICAL RULES:
- Extract EXACTLY what you see - do not round or modify numbers
- PRESERVE ALL DECIMAL PLACES - if you see 0.78721, return "0.78721" not "0.7872"
- Include EVERY digit visible in the price, including trailing zeros
- Include ALL visible price levels, even if partially visible
- If unsure about a price, include it in notes
- For {direction} trades: {"TPs should be LOWER than entry, SL HIGHER" if side == "Sell" else "TPs should be HIGHER than entry, SL LOWER"}
- Double-check mobile screenshots for small text near chart edges
- Conservative strategy needs at least 3 entries OR 4 TPs visible
- IMPORTANT: Extract the FULL PRECISION of each number - all decimal places

ENHANCED ANALYSIS REQUIREMENTS:
- Before the JSON output, provide a detailed description of what you observe
- Explain your reasoning for each price identification
- Note any difficulties in reading specific values
- Describe the confidence level for each extracted price
- Use all available tokens to provide comprehensive analysis"""

    async def _parse_openai_response(self, content: str, symbol: str, side: str) -> Dict[str, Any]:
        """Parse OpenAI response and convert to internal format with enhanced null handling"""
        try:
            import json
            from decimal import Decimal

            # Custom JSON decoder that preserves decimal precision
            def parse_json_with_decimal(json_str):
                """Parse JSON preserving decimal precision for price fields"""
                # Parse with object_pairs_hook to intercept all values
                def decimal_parser(pairs):
                    result = {}
                    for key, value in pairs:
                        # Check if this is a price field and value is a string
                        if isinstance(value, str) and any(price_key in key for price_key in ['price', 'entry', 'tp', 'sl']):
                            try:
                                # Preserve exact decimal representation
                                result[key] = value  # Keep as string for now
                            except:
                                result[key] = value
                        else:
                            result[key] = value
                    return result

                return json.loads(json_str, object_pairs_hook=decimal_parser)

            # Try to extract JSON from response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()

            # Log raw response for debugging
            logger.info(f"Raw OpenAI response: {content[:500]}...")  # First 500 chars

            # Parse JSON response with custom parser
            result = parse_json_with_decimal(content)

            if not result.get("success"):
                return self._error_result(result.get("notes", "Analysis failed"))

            # Convert parameters to internal format
            params = result.get("parameters", {})
            strategy_type = result.get("strategy_type", "fast")

            # Map to internal constants
            internal_params = {}

            # Helper function to safely convert to Decimal
            def safe_decimal_convert(value, field_name):
                try:
                    if value is None or value == "" or value == "null":
                        logger.warning(f"{field_name} is empty or None")
                        return None
                    # Clean the value string
                    clean_value = str(value).strip().replace(',', '').replace('$', '')
                    return Decimal(clean_value)
                except (InvalidOperation, ValueError) as e:
                    logger.error(f"Failed to convert {field_name}='{value}' to Decimal: {e}")
                    return None

            # Entry prices
            if "primary_entry" in params:
                val = safe_decimal_convert(params["primary_entry"], "primary_entry")
                if val:
                    internal_params[PRIMARY_ENTRY_PRICE] = val

            if strategy_type == "conservative":
                if "limit_entry_1" in params:
                    val = safe_decimal_convert(params["limit_entry_1"], "limit_entry_1")
                    if val:
                        internal_params[LIMIT_ENTRY_1_PRICE] = val
                if "limit_entry_2" in params:
                    val = safe_decimal_convert(params["limit_entry_2"], "limit_entry_2")
                    if val:
                        internal_params[LIMIT_ENTRY_2_PRICE] = val
                if "limit_entry_3" in params:
                    val = safe_decimal_convert(params["limit_entry_3"], "limit_entry_3")
                    if val:
                        internal_params[LIMIT_ENTRY_3_PRICE] = val

            # Take profits with enhanced handling for missing TP4
            if "tp1_price" in params:
                val = safe_decimal_convert(params["tp1_price"], "tp1_price")
                if val:
                    internal_params[TP1_PRICE] = val
            if "tp2_price" in params and strategy_type == "conservative":
                val = safe_decimal_convert(params["tp2_price"], "tp2_price")
                if val:
                    internal_params[TP2_PRICE] = val
            if "tp3_price" in params and strategy_type == "conservative":
                val = safe_decimal_convert(params["tp3_price"], "tp3_price")
                if val:
                    internal_params[TP3_PRICE] = val
            if "tp4_price" in params and strategy_type == "conservative":
                val = safe_decimal_convert(params["tp4_price"], "tp4_price")
                if val:
                    internal_params[TP4_PRICE] = val
                elif strategy_type == "conservative" and TP3_PRICE in internal_params:
                    # Calculate TP4 if missing in conservative mode
                    tp3 = internal_params[TP3_PRICE]
                    entry = internal_params.get(PRIMARY_ENTRY_PRICE)
                    if tp3 and entry:
                        # Calculate TP4 as TP3 + 50% of (TP3 - Entry) distance
                        distance = tp3 - entry
                        calculated_tp4 = tp3 + (distance * Decimal("0.5"))
                        internal_params[TP4_PRICE] = calculated_tp4
                        logger.info(f"Calculated missing TP4: {calculated_tp4} based on TP3: {tp3}")

            # Stop loss
            if "sl_price" in params:
                val = safe_decimal_convert(params["sl_price"], "sl_price")
                if val:
                    internal_params[SL_PRICE] = val

            # Leverage and margin with better error handling
            try:
                internal_params["leverage"] = int(params.get("leverage", 10))
            except (ValueError, TypeError):
                internal_params["leverage"] = 10

            margin_val = safe_decimal_convert(params.get("margin_amount", 100), "margin_amount")
            internal_params["margin_amount"] = margin_val if margin_val else Decimal("100")

            # Check if we have minimum required parameters
            missing_critical = []
            if PRIMARY_ENTRY_PRICE not in internal_params:
                missing_critical.append("entry price")
            if TP1_PRICE not in internal_params:
                missing_critical.append("take profit 1")
            if SL_PRICE not in internal_params:
                missing_critical.append("stop loss")

            if missing_critical:
                logger.error(f"Missing critical parameters: {', '.join(missing_critical)}")
                return self._error_result(f"Failed to extract required parameters: {', '.join(missing_critical)}")

            # For conservative strategy, ensure we have all required TPs
            if strategy_type == "conservative":
                if TP4_PRICE not in internal_params:
                    logger.warning("TP4 was missing and calculated automatically")

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

            # Include enhanced analysis data if available
            enhanced_data = {}
            if "reasoning" in result:
                enhanced_data["reasoning"] = result["reasoning"]
                logger.info(f"Enhanced reasoning: {result['reasoning'][:200]}...")  # Log first 200 chars
            if "visible_elements" in result:
                enhanced_data["visible_elements"] = result["visible_elements"]

            return_data = {
                "success": True,
                "confidence": result.get("confidence", 0.8),
                "strategy_type": strategy_type,
                "parameters": validated_params,  # Use validated/corrected params
                "notes": result.get("notes", "Analysis completed successfully")
            }

            # Add enhanced data if available
            if enhanced_data:
                return_data["enhanced_analysis"] = enhanced_data

            return return_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Content that failed to parse: {content}")
            return self._error_result(f"Invalid JSON response from AI: {escape(str(e))}")
        except (ValueError, InvalidOperation) as e:
            logger.error(f"Value conversion error: {e}")
            logger.error(f"Parameters that caused error: {params}")
            return self._error_result(f"Failed to convert values: {escape(str(e))}")
        except Exception as e:
            logger.error(f"Unexpected error in parse_openai_response: {e}")
            logger.error(f"Full traceback:", exc_info=True)
            return self._error_result(f"Unexpected parsing error: {escape(str(e))}")

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

    async def _aggressive_enhance_for_ocr(self, image: Image.Image) -> Image.Image:
        """Apply aggressive enhancement for very poor quality images"""
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Check if this is a dark image
            gray = image.convert('L')
            pixels = np.array(gray)
            mean_brightness = np.mean(pixels)
            width, height = image.size
            is_mobile = height > width and width < 800

            # Super aggressive processing for very dark mobile screenshots
            if mean_brightness < 30 and is_mobile:
                logger.info(f"Very dark mobile image detected (brightness: {mean_brightness}), applying SUPER aggressive processing")

                # Save multiple versions and pick the best
                versions = []

                # Version 1: Extreme brightness + gamma
                v1 = image.copy()
                enhancer = ImageEnhance.Brightness(v1)
                v1 = enhancer.enhance(6.0)  # Even more brightness
                img_array = np.array(v1)
                gamma = 3.5  # More aggressive gamma
                img_array = np.power(img_array / 255.0, 1.0 / gamma) * 255.0
                img_array = np.clip(img_array, 0, 255).astype(np.uint8)
                v1 = Image.fromarray(img_array)
                v1 = ImageOps.equalize(v1)
                versions.append(("brightness_gamma", v1))

                # Version 2: Inversion + enhancement
                v2 = image.copy()
                # Pre-brighten before inversion
                enhancer = ImageEnhance.Brightness(v2)
                v2 = enhancer.enhance(3.0)
                v2 = ImageOps.invert(v2)
                enhancer = ImageEnhance.Contrast(v2)
                v2 = enhancer.enhance(3.0)
                # Sharpen text
                v2 = v2.filter(ImageFilter.UnsharpMask(radius=2, percent=250, threshold=1))
                versions.append(("inverted", v2))

                # Version 3: Threshold-based approach
                v3 = image.copy()
                enhancer = ImageEnhance.Brightness(v3)
                v3 = enhancer.enhance(4.0)
                # Convert to grayscale and apply adaptive threshold
                gray_v3 = v3.convert('L')
                pixels_v3 = np.array(gray_v3)
                # Adaptive threshold
                threshold = np.mean(pixels_v3) + 0.5 * np.std(pixels_v3)
                binary = gray_v3.point(lambda x: 255 if x > threshold else 0, 'L')
                v3 = binary.convert('RGB')
                versions.append(("threshold", v3))

                # Pick the version with best contrast
                best_contrast = 0
                best_version = image
                best_name = "original"

                for name, ver in versions:
                    gray_ver = np.array(ver.convert('L'))
                    contrast = np.std(gray_ver)
                    logger.info(f"Version {name} contrast: {contrast}")
                    if contrast > best_contrast:
                        best_contrast = contrast
                        best_version = ver
                        best_name = name

                logger.info(f"Selected {best_name} version with contrast {best_contrast}")
                image = best_version

            elif mean_brightness < 30:
                logger.info(f"Very dark image detected (brightness: {mean_brightness}), applying aggressive brightening")
                # Standard aggressive enhancement for non-mobile
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(4.0)

                img_array = np.array(image)
                gamma = 2.2
                img_array = np.power(img_array / 255.0, 1.0 / gamma) * 255.0
                img_array = np.clip(img_array, 0, 255).astype(np.uint8)
                image = Image.fromarray(img_array)

                image = ImageOps.autocontrast(image, cutoff=5)
            elif mean_brightness < 60:
                logger.info(f"Dark image detected (brightness: {mean_brightness}), applying moderate brightening")
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(2.0)
                image = ImageOps.autocontrast(image, cutoff=3)

            # Aggressive contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.5 if is_mobile else 2.0)

            # Color reduction for text clarity
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(0.3 if is_mobile else 0.5)

            # Strong sharpening for mobile
            if is_mobile:
                # Apply multiple sharpening passes
                for _ in range(2):
                    image = image.filter(ImageFilter.SHARPEN)
                image = image.filter(ImageFilter.UnsharpMask(radius=4, percent=300, threshold=2))
            else:
                image = image.filter(ImageFilter.UnsharpMask(radius=3, percent=200, threshold=3))

            # Edge enhancement
            image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)

            # Aggressive upscaling for mobile screenshots
            if width < 800 or (is_mobile and width < 1000):
                target_width = 1200 if is_mobile else 1024
                scale_factor = target_width / width
                new_size = (int(width * scale_factor), int(height * scale_factor))
                logger.info(f"Upscaling low-res image from {width}x{height} to {new_size[0]}x{new_size[1]}")
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            return image

        except Exception as e:
            logger.error(f"Error in aggressive enhancement: {e}")
            return image  # Return original if enhancement fails

    def _create_simple_analysis_prompt(self, symbol: str, side: str) -> str:
        """Create simplified prompt focusing on visible numbers - optimized for speed"""
        direction = "LONG" if side == "Buy" else "SHORT"
        box_color = "GREEN" if side == "Buy" else "RED"

        return f"""Extract trading prices from this {symbol} {direction} screenshot.

LOOK FOR:
- {box_color} BOXES = Entry/TP prices
- GREY BOX = Stop Loss
- Labels: {"'add long'" if side == "Buy" else "'add short'"}, "GGshot: Take Profit", "GGshot: Trailing Stop Loss"

{direction} POSITIONS:
{"- Entries: GREEN boxes BELOW current price" if side == "Buy" else "- Entries: RED boxes ABOVE current price"}
{"- TPs: GREEN boxes ABOVE entries" if side == "Buy" else "- TPs: RED boxes BELOW entries"}
{"- SL: GREY box at BOTTOM" if side == "Buy" else "- SL: GREY box at TOP"}

Return JSON:
{{
    "success": true,
    "confidence": 0.0-1.0,
    "strategy_type": "conservative" or "fast",
    "parameters": {{
        "primary_entry": "price",
        "limit_entry_1": "price",
        "limit_entry_2": "price",
        "limit_entry_3": "price",
        "tp1_price": "price",
        "tp2_price": "price",
        "tp3_price": "price",
        "tp4_price": "price",
        "sl_price": "price"
    }}
}}

Extract EXACT numbers with ALL decimals."""

    def _create_numbers_only_prompt(self) -> str:
        """Create minimal prompt to just extract numbers"""
        return """You are a number extraction specialist focusing on LABELED PRICES and COLORED BOXES in trading screenshots.

YOUR TASK:
1. Look for TEXT LABELS next to prices:
   - "add short" or "add long" = ENTRY PRICE
   - "GGshot: Take Profit" = TAKE PROFIT PRICE
   - "GGshot: Trailing Stop Loss" = STOP LOSS PRICE
2. Find ALL numbers inside GREEN BOXES (green rectangular backgrounds) - for LONG trades
3. Find ALL numbers inside RED BOXES (red rectangular backgrounds) - for SHORT trades
4. Find ALL numbers inside GREY/GRAY BOXES (grey rectangular backgrounds) - always Stop Loss
5. Note the label and position of each price

CRITICAL:
- TEXT LABELS are the primary way to identify price types
- The COLOR of the box confirms:
  * GREEN = Entry/TP for LONG trades
  * RED = Entry/TP for SHORT trades
  * GREY = Stop Loss (for both)

Return JSON format:
{
    "numbers_found": [
        {"value": "1.2345", "box_color": "green", "label": "add long", "position": "top", "context": "entry price with 'add long' label"},
        {"value": "1.2000", "box_color": "green", "label": "GGshot: Take Profit", "position": "middle", "context": "TP with label"},
        {"value": "1.1500", "box_color": "green", "label": "GGshot: Take Profit", "position": "lower", "context": "TP with label"},
        {"value": "1.3000", "box_color": "grey", "label": "GGshot: Trailing Stop Loss", "position": "top", "context": "stop loss with label"}
    ],
    "green_box_count": 3,
    "red_box_count": 0,
    "grey_box_count": 1,
    "confidence": 0.0-1.0
}

IMPORTANT: Focus ONLY on numbers inside colored boxes. Extract EXACT values."""

    async def _emergency_number_extraction(self, base64_image: str, symbol: str, side: str) -> Dict[str, Any]:
        """Emergency extraction - just get ANY visible numbers"""
        try:
            prompt = """Extract ALL numbers you can see in this image. Return them in a simple list format:
{
    "numbers": [
        "number1",
        "number2",
        "number3"
    ]
}

Include ANY number you see, even partial ones. Focus on price-like numbers (with decimals)."""

            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "List all numbers visible in this trading screenshot."},
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
                max_tokens=500,
                temperature=0.1
            )

            content = response.choices[0].message.content
            logger.info(f"Emergency extraction response: {content}")

            # Clean JSON response - handle multiple markdown formats
            if '```' in content:
                # Extract content between backticks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                else:
                    # Just remove backticks
                    content = content.replace('```json', '').replace('```', '').strip()

            # Try to parse and make sense of the numbers
            import json
            data = json.loads(content)
            numbers = data.get("numbers", [])

            if len(numbers) >= 3:
                # Convert to decimals and sort
                decimals = []
                for num in numbers:
                    try:
                        val = Decimal(str(num).replace(',', ''))
                        decimals.append(val)
                    except:
                        continue

                if len(decimals) >= 3:
                    decimals.sort()
                    # Assume middle is entry, highest is TP, lowest is SL
                    return {
                        "success": True,
                        "confidence": 0.3,  # Low confidence
                        "strategy_type": "fast",
                        "parameters": {
                            PRIMARY_ENTRY_PRICE: decimals[len(decimals)//2],
                            TP1_PRICE: decimals[-1],
                            SL_PRICE: decimals[0],
                            "leverage": 10,
                            "margin_amount": Decimal("100")
                        },
                        "notes": "Emergency extraction - parameters guessed from visible numbers"
                    }

            return self._error_result("Could not extract enough numbers")

        except Exception as e:
            logger.error(f"Emergency extraction failed: {e}")
            return self._error_result(f"Emergency extraction error: {str(e)}")

    async def _parse_numbers_only_response(self, content: str, symbol: str, side: str) -> Dict[str, Any]:
        """Parse response from numbers-only extraction using colored box information"""
        try:
            import json

            # Clean JSON response
            if content.startswith('```'):
                content = content.replace('```json', '').replace('```', '').strip()

            data = json.loads(content)
            numbers_found = data.get("numbers_found", [])

            if not numbers_found:
                return self._error_result("No numbers found in colored boxes")

            # First pass: collect all prices to understand the scale
            all_prices = []
            for item in numbers_found:
                try:
                    value = Decimal(str(item["value"]).replace(',', ''))
                    all_prices.append(value)
                except:
                    continue

            # Separate by label and box color
            entry_prices = []
            tp_prices = []
            sl_price = None

            for item in numbers_found:
                try:
                    value = Decimal(str(item["value"]).replace(',', ''))
                    box_color = item.get("box_color", "").lower()
                    label = item.get("label", "").lower()
                    position = item.get("position", "")

                    # Use label as primary identifier
                    if "trailing stop loss" in label or ("grey" in box_color or "gray" in box_color):
                        sl_price = value
                        logger.info(f"Found SL from label/grey box: {value}")
                    elif "add short" in label or "add long" in label:
                        # Normalize entry prices that may be missing decimal points
                        # Get context from other prices that have decimals
                        decimal_prices = [p for p in all_prices if p < 10]
                        if decimal_prices and value > 100:
                            # Calculate average scale of decimal prices
                            avg_decimal = sum(decimal_prices) / len(decimal_prices)
                            # Determine normalization factor
                            if 1000 <= value < 10000:
                                normalized_value = value / 10000  # 1717 -> 0.1717
                            elif 100 <= value < 1000:
                                normalized_value = value / 1000   # 171 -> 0.171
                            else:
                                normalized_value = value / 100    # 17 -> 0.17

                            # Verify normalized value is in reasonable range of other prices
                            if normalized_value > avg_decimal * 0.1 and normalized_value < avg_decimal * 10:
                                logger.info(f"Normalizing entry price: {value} -> {normalized_value} (context: avg decimal price {avg_decimal:.4f})")
                                value = normalized_value
                            else:
                                logger.warning(f"Normalized value {normalized_value} out of range, keeping original {value}")
                        entry_prices.append((value, position))
                        logger.info(f"Found entry from 'add' label: {value}")
                    elif "take profit" in label:
                        tp_prices.append((value, position))
                        logger.info(f"Found TP from 'take profit' label: {value}")
                    elif "red" in box_color or "green" in box_color:
                        # If no label but colored box (red for short, green for long)
                        # we'll determine based on position later
                        logger.info(f"Found unlabeled {box_color} box value: {value}")
                except:
                    continue


            if not sl_price:
                return self._error_result("No stop loss found (should have 'GG-Shot:Trailing Stop Loss' label)")

            # Sort entries and TPs based on labels
            if side == "Sell":
                # For SHORT trades
                # Sort entries: lowest to highest (primary entry is lowest/closest to market)
                entries = sorted([v for v, _ in entry_prices])
                # Sort TPs: highest to lowest
                tps = sorted([v for v, _ in tp_prices], reverse=True)

            else:  # Buy/LONG
                # For LONG trades
                # Sort entries: highest to lowest (primary entry is highest/closest to market)
                entries = sorted([v for v, _ in entry_prices], reverse=True)
                # Sort TPs: lowest to highest
                tps = sorted([v for v, _ in tp_prices])

            # Determine strategy type
            strategy_type = "conservative" if len(entries) >= 3 or len(tps) >= 4 else "fast"

            # Build parameters
            internal_params = {
                SL_PRICE: sl_price,
                "leverage": 10,
                "margin_amount": Decimal("100")
            }

            # Add entries
            if entries:
                internal_params[PRIMARY_ENTRY_PRICE] = entries[0]
                if len(entries) > 1 and strategy_type == "conservative":
                    internal_params[LIMIT_ENTRY_1_PRICE] = entries[1]
                if len(entries) > 2:
                    internal_params[LIMIT_ENTRY_2_PRICE] = entries[2]
                if len(entries) > 3:
                    internal_params[LIMIT_ENTRY_3_PRICE] = entries[3]

            # Add TPs
            if tps:
                internal_params[TP1_PRICE] = tps[0]
                if len(tps) > 1 and strategy_type == "conservative":
                    internal_params[TP2_PRICE] = tps[1]
                if len(tps) > 2:
                    internal_params[TP3_PRICE] = tps[2]
                if len(tps) > 3:
                    internal_params[TP4_PRICE] = tps[3]

            # Validate we have minimum requirements
            if PRIMARY_ENTRY_PRICE not in internal_params or TP1_PRICE not in internal_params:
                return self._error_result("Missing required entry or TP1")

            return {
                "success": True,
                "confidence": 0.9,  # Higher confidence with color information
                "strategy_type": strategy_type,
                "parameters": internal_params,
                "notes": f"Found {len(entries)} entries with 'add' labels, {len(tps)} TPs with 'GG-Shot' labels, SL with trailing stop label"
            }

        except Exception as e:
            logger.error(f"Error parsing numbers-only response: {e}")
            return self._error_result("Failed to parse colored box numbers")

    async def _calculate_extraction_confidence(self, result: Dict[str, Any],
                                             symbol: str, side: str) -> float:
        """
        Calculate composite confidence score for extraction result

        Weights:
        - Field completeness: 40%
        - Logical consistency: 30%
        - Price relationships: 20%
        - OpenAI confidence: 10%
        """
        if not result.get("success"):
            return 0.0

        params = result.get("parameters", {})
        strategy = result.get("strategy_type", "fast")
        scores = {}

        # 1. Field Completeness (40%)
        required_fields = [PRIMARY_ENTRY_PRICE, TP1_PRICE, SL_PRICE]
        if strategy == "conservative":
            required_fields.extend([TP2_PRICE, TP3_PRICE, TP4_PRICE])

        present_fields = sum(1 for field in required_fields if field in params)
        field_completeness = present_fields / len(required_fields)
        scores["field_completeness"] = field_completeness * 0.4

        # 2. Logical Consistency (30%)
        logic_score = 1.0

        # Check entry vs SL relationship
        if PRIMARY_ENTRY_PRICE in params and SL_PRICE in params:
            entry = params[PRIMARY_ENTRY_PRICE]
            sl = params[SL_PRICE]

            # Check for potential decimal point issues
            if entry > 100 and sl < 10:
                # Likely decimal point issue with entry price
                logger.warning(f"Potential decimal point issue: entry={entry}, sl={sl}")
                # Try to normalize entry price
                if 1000 <= entry < 10000:
                    entry = entry / 10000
                elif 100 <= entry < 1000:
                    entry = entry / 1000
                params[PRIMARY_ENTRY_PRICE] = entry
                logger.info(f"Auto-corrected entry price to {entry}")

            if side == "Buy":
                if sl >= entry:
                    logic_score *= 0.0  # Critical failure
                    logger.warning(f"Buy SL ({sl}) >= entry ({entry})")
            else:  # Sell
                if sl <= entry:
                    logic_score *= 0.0  # Critical failure
                    logger.warning(f"Sell SL ({sl}) <= entry ({entry})")
        else:
            logic_score *= 0.5  # Missing critical fields

        # Check TP vs entry relationship
        if PRIMARY_ENTRY_PRICE in params and TP1_PRICE in params:
            entry = params[PRIMARY_ENTRY_PRICE]
            tp1 = params[TP1_PRICE]

            # Check for potential decimal point issues
            if entry > 100 and tp1 < 10:
                # Likely decimal point issue with entry price
                logger.warning(f"Potential decimal point issue in TP check: entry={entry}, tp1={tp1}")
                # Use the corrected entry if available
                if PRIMARY_ENTRY_PRICE in params:
                    entry = params[PRIMARY_ENTRY_PRICE]

            if side == "Buy":
                if tp1 <= entry:
                    logic_score *= 0.3
                    logger.warning(f"Buy TP1 ({tp1}) <= entry ({entry})")
            else:  # Sell
                if tp1 >= entry:
                    logic_score *= 0.3
                    logger.warning(f"Sell TP1 ({tp1}) >= entry ({entry})")

        # Check TP ordering for conservative
        if strategy == "conservative":
            tps = [params.get(tp) for tp in [TP1_PRICE, TP2_PRICE, TP3_PRICE, TP4_PRICE]
                   if tp in params]
            if len(tps) >= 2:
                if side == "Buy":
                    # TPs should be ascending
                    if not all(tps[i] <= tps[i+1] for i in range(len(tps)-1)):
                        logic_score *= 0.7
                        logger.warning("Buy TPs not in ascending order")
                else:  # Sell
                    # TPs should be descending
                    if not all(tps[i] >= tps[i+1] for i in range(len(tps)-1)):
                        logic_score *= 0.7
                        logger.warning("Sell TPs not in descending order")

        scores["logical_consistency"] = logic_score * 0.3

        # 3. Price Relationships (20%)
        relationship_score = 1.0

        if all(field in params for field in [PRIMARY_ENTRY_PRICE, TP1_PRICE, SL_PRICE]):
            entry = params[PRIMARY_ENTRY_PRICE]
            tp1 = params[TP1_PRICE]
            sl = params[SL_PRICE]

            # Check price distances
            tp_distance = abs((tp1 - entry) / entry)
            sl_distance = abs((sl - entry) / entry)

            # Penalize if distances are too small (<0.1%) or too large (>50%)
            if tp_distance < Decimal("0.001"):
                relationship_score *= 0.5
                logger.warning(f"TP1 too close to entry: {tp_distance:.4%}")
            elif tp_distance > Decimal("0.5"):
                relationship_score *= 0.7
                logger.warning(f"TP1 too far from entry: {tp_distance:.4%}")

            if sl_distance < Decimal("0.001"):
                relationship_score *= 0.5
                logger.warning(f"SL too close to entry: {sl_distance:.4%}")
            elif sl_distance > Decimal("0.5"):
                relationship_score *= 0.7
                logger.warning(f"SL too far from entry: {sl_distance:.4%}")

            # Check risk/reward ratio
            if side == "Buy":
                risk = entry - sl
                reward = tp1 - entry
            else:
                risk = sl - entry
                reward = entry - tp1

            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio < Decimal("0.5"):
                    relationship_score *= 0.6
                    logger.warning(f"Poor R:R ratio: {rr_ratio:.2f}:1")
                elif rr_ratio > Decimal("10"):
                    relationship_score *= 0.8
                    logger.warning(f"Unrealistic R:R ratio: {rr_ratio:.2f}:1")
        else:
            relationship_score = 0.5  # Missing fields for calculation

        scores["price_relationships"] = relationship_score * 0.2

        # 4. OpenAI Confidence (10%)
        openai_confidence = float(result.get("confidence", 0.5))
        scores["openai_confidence"] = openai_confidence * 0.1

        # Calculate total
        total_confidence = sum(scores.values())

        # Log breakdown
        logger.info(f"Confidence breakdown: Field={scores['field_completeness']:.2f}, "
                   f"Logic={scores['logical_consistency']:.2f}, "
                   f"Relationships={scores['price_relationships']:.2f}, "
                   f"OpenAI={scores['openai_confidence']:.2f}, "
                   f"Total={total_confidence:.2f}")

        return total_confidence

    def _identify_missing_fields(self, result: Dict[str, Any]) -> List[str]:
        """Identify which critical fields are missing from extraction"""
        if not result or not result.get("success"):
            return ["all"]

        params = result.get("parameters", {})
        strategy = result.get("strategy_type", "fast")
        missing = []

        # Check required fields
        if PRIMARY_ENTRY_PRICE not in params:
            missing.append("primary_entry")
        if TP1_PRICE not in params:
            missing.append("tp1")
        if SL_PRICE not in params:
            missing.append("sl")

        # Check conservative strategy fields
        if strategy == "conservative":
            if LIMIT_ENTRY_1_PRICE not in params:
                missing.append("limit_entries")
            if TP4_PRICE not in params:
                missing.append("tp4")

        return missing

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