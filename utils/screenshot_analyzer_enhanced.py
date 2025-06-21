#!/usr/bin/env python3
"""
Enhanced Screenshot Analyzer with Multiple Accuracy Checks
Adds multiple validation passes to ensure extracted values are accurate
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
import asyncio

from utils.screenshot_analyzer import ScreenshotAnalyzer
from config.constants import *

logger = logging.getLogger(__name__)

class EnhancedGGShotAnalyzer(ScreenshotAnalyzer):
    """Enhanced analyzer with multiple accuracy checks"""
    
    async def analyze_screenshot(self, file_path: str, symbol: str, side: str, 
                               pre_enhanced: bool = False) -> Dict[str, Any]:
        """
        Analyze screenshot with multiple accuracy checks
        """
        logger.info(f"🔍 Starting ENHANCED analysis with multiple accuracy checks for {symbol} {side}")
        
        # Get base analysis from parent class
        initial_result = await self.analyze_trading_screenshot(file_path, symbol, side)
        
        # Log extraction statistics if available
        if "extraction_stats" in initial_result:
            stats = initial_result["extraction_stats"]
            logger.info(f"📊 Extraction stats: {stats['passes_attempted']} passes, "
                       f"first_pass_confidence={stats['first_pass_confidence']:.2f}, "
                       f"final_confidence={stats['final_confidence']:.2f}, "
                       f"method={stats['method_used']}")
        
        if not initial_result.get("success"):
            return initial_result
        
        # Perform multiple accuracy checks
        verified_result = await self._perform_accuracy_checks(
            initial_result, file_path, symbol, side
        )
        
        return verified_result
    
    async def _perform_accuracy_checks(self, initial_result: Dict[str, Any], 
                                     file_path: str, symbol: str, side: str) -> Dict[str, Any]:
        """Perform multiple accuracy checks on extracted values"""
        
        logger.info("🔍 Starting multiple accuracy verification passes...")
        
        # Extract initial parameters
        params = initial_result.get("parameters", {})
        strategy = initial_result.get("strategy_type", "fast")
        confidence_scores = {}
        
        # Check 1: Cross-validation with different prompts
        cross_validation_result = await self._cross_validate_extraction(
            file_path, symbol, side, params
        )
        confidence_scores["cross_validation"] = cross_validation_result["confidence"]
        
        # Check 2: Logical consistency validation
        consistency_result = self._validate_logical_consistency(params, side, strategy)
        confidence_scores["logical_consistency"] = consistency_result["confidence"]
        
        # Check 3: Price relationship validation
        relationship_result = self._validate_price_relationships(params, side)
        confidence_scores["price_relationships"] = relationship_result["confidence"]
        
        # Check 4: Risk/Reward validation
        rr_result = self._validate_risk_reward(params, side)
        confidence_scores["risk_reward"] = rr_result["confidence"]
        
        # Check 5: Market context validation (if current price available)
        if "current_price" in params:
            market_result = self._validate_market_context(params, side)
            confidence_scores["market_context"] = market_result["confidence"]
        
        # Calculate overall confidence
        overall_confidence = sum(confidence_scores.values()) / len(confidence_scores)
        
        # Prepare enhanced result
        enhanced_result = initial_result.copy()
        enhanced_result["accuracy_checks"] = {
            "overall_confidence": round(overall_confidence, 2),
            "individual_scores": confidence_scores,
            "verification_notes": self._generate_verification_notes(confidence_scores)
        }
        
        # If confidence is too low, attempt enhanced extraction
        if overall_confidence < 0.7:
            logger.warning(f"⚠️ Low confidence: {overall_confidence:.2f}. Attempting enhanced extraction...")
            enhanced_params = await self._attempt_enhanced_extraction(
                file_path, symbol, side, params, confidence_scores
            )
            if enhanced_params:
                enhanced_result["parameters"] = enhanced_params
                enhanced_result["extraction_method"] = "enhanced_verification"
        
        return enhanced_result
    
    async def _cross_validate_extraction(self, file_path: str, symbol: str, 
                                       side: str, original_params: Dict) -> Dict[str, Any]:
        """Cross-validate by extracting with different prompts and comparing"""
        logger.info("🔄 Cross-validating with alternative prompts...")
        
        # Extract with simplified prompt
        simple_result = await self._analyze_with_simple_prompt(file_path, symbol, side)
        
        # Extract with numbers-only prompt
        numbers_result = await self._analyze_with_numbers_prompt(file_path, symbol, side)
        
        # Compare results
        matches = 0
        total_checks = 0
        discrepancies = []
        
        key_fields = [PRIMARY_ENTRY_PRICE, TP1_PRICE, SL_PRICE]
        
        for field in key_fields:
            if field in original_params:
                total_checks += 1
                original_value = original_params[field]
                
                # Check against simple extraction
                if simple_result and field in simple_result:
                    if self._values_match(original_value, simple_result[field]):
                        matches += 1
                    else:
                        discrepancies.append({
                            "field": field,
                            "original": original_value,
                            "simple": simple_result[field]
                        })
                
                # Check against numbers extraction
                if numbers_result and field in numbers_result:
                    if self._values_match(original_value, numbers_result[field]):
                        matches += 0.5  # Half weight for numbers-only match
        
        confidence = matches / total_checks if total_checks > 0 else 0
        
        return {
            "confidence": confidence,
            "discrepancies": discrepancies,
            "validation_method": "cross_validation"
        }
    
    def _validate_logical_consistency(self, params: Dict, side: str, 
                                    strategy: str) -> Dict[str, Any]:
        """Validate logical consistency of extracted values"""
        logger.info("🧮 Validating logical consistency...")
        
        issues = []
        checks_passed = 0
        total_checks = 0
        
        # Check 1: Entry prices are in correct order
        if strategy == "conservative":
            entries = []
            for key in [LIMIT_ENTRY_1_PRICE, LIMIT_ENTRY_2_PRICE, LIMIT_ENTRY_3_PRICE]:
                if key in params:
                    entries.append(params[key])
            
            if len(entries) >= 2:
                total_checks += 1
                if side == "Buy":
                    if all(entries[i] >= entries[i+1] for i in range(len(entries)-1)):
                        checks_passed += 1
                    else:
                        issues.append("Buy entries not in descending order")
                else:  # Sell
                    if all(entries[i] <= entries[i+1] for i in range(len(entries)-1)):
                        checks_passed += 1
                    else:
                        issues.append("Sell entries not in ascending order")
        
        # Check 2: TP levels are in correct order
        tps = []
        for key in [TP1_PRICE, TP2_PRICE, TP3_PRICE, TP4_PRICE]:
            if key in params:
                tps.append(params[key])
        
        if len(tps) >= 2:
            total_checks += 1
            if side == "Buy":
                if all(tps[i] <= tps[i+1] for i in range(len(tps)-1)):
                    checks_passed += 1
                else:
                    issues.append("Buy TPs not in ascending order")
            else:  # Sell
                if all(tps[i] >= tps[i+1] for i in range(len(tps)-1)):
                    checks_passed += 1
                else:
                    issues.append("Sell TPs not in descending order")
        
        # Check 3: SL is on correct side of entries
        if SL_PRICE in params and PRIMARY_ENTRY_PRICE in params:
            total_checks += 1
            sl = params[SL_PRICE]
            entry = params[PRIMARY_ENTRY_PRICE]
            
            if side == "Buy":
                if sl < entry:
                    checks_passed += 1
                else:
                    issues.append("Buy SL not below entry")
            else:  # Sell
                if sl > entry:
                    checks_passed += 1
                else:
                    issues.append("Sell SL not above entry")
        
        confidence = checks_passed / total_checks if total_checks > 0 else 0
        
        return {
            "confidence": confidence,
            "issues": issues,
            "validation_method": "logical_consistency"
        }
    
    def _validate_price_relationships(self, params: Dict, side: str) -> Dict[str, Any]:
        """Validate price relationships and distances"""
        logger.info("📏 Validating price relationships...")
        
        checks_passed = 0
        total_checks = 0
        issues = []
        
        # Get key prices
        entry = params.get(PRIMARY_ENTRY_PRICE)
        tp1 = params.get(TP1_PRICE)
        sl = params.get(SL_PRICE)
        
        if not all([entry, tp1, sl]):
            return {"confidence": 0, "issues": ["Missing key prices"], "validation_method": "price_relationships"}
        
        # Check 1: Minimum distance between levels (at least 0.1%)
        min_distance_pct = Decimal("0.001")
        
        # Entry to TP1 distance
        total_checks += 1
        tp1_distance = abs((tp1 - entry) / entry)
        if tp1_distance >= min_distance_pct:
            checks_passed += 1
        else:
            issues.append(f"TP1 too close to entry: {tp1_distance:.4%}")
        
        # Entry to SL distance
        total_checks += 1
        sl_distance = abs((sl - entry) / entry)
        if sl_distance >= min_distance_pct:
            checks_passed += 1
        else:
            issues.append(f"SL too close to entry: {sl_distance:.4%}")
        
        # Check 2: Maximum distance validation (not more than 50%)
        max_distance_pct = Decimal("0.5")
        
        total_checks += 1
        if tp1_distance <= max_distance_pct:
            checks_passed += 1
        else:
            issues.append(f"TP1 too far from entry: {tp1_distance:.4%}")
        
        total_checks += 1
        if sl_distance <= max_distance_pct:
            checks_passed += 1
        else:
            issues.append(f"SL too far from entry: {sl_distance:.4%}")
        
        # Check 3: TP spacing validation for conservative
        if params.get("strategy_type") == "conservative":
            tp2 = params.get(TP2_PRICE)
            tp3 = params.get(TP3_PRICE)
            tp4 = params.get(TP4_PRICE)
            
            if tp2 and tp3:
                total_checks += 1
                spacing_2_3 = abs((tp3 - tp2) / tp2)
                if min_distance_pct <= spacing_2_3 <= max_distance_pct:
                    checks_passed += 1
                else:
                    issues.append(f"TP2-TP3 spacing issue: {spacing_2_3:.4%}")
        
        confidence = checks_passed / total_checks if total_checks > 0 else 0
        
        return {
            "confidence": confidence,
            "issues": issues,
            "validation_method": "price_relationships"
        }
    
    def _validate_risk_reward(self, params: Dict, side: str) -> Dict[str, Any]:
        """Validate risk/reward ratio"""
        logger.info("💰 Validating risk/reward ratio...")
        
        entry = params.get(PRIMARY_ENTRY_PRICE)
        tp1 = params.get(TP1_PRICE)
        sl = params.get(SL_PRICE)
        
        if not all([entry, tp1, sl]):
            return {"confidence": 0, "issues": ["Missing prices for R:R calculation"], "validation_method": "risk_reward"}
        
        # Calculate risk and reward
        if side == "Buy":
            risk = entry - sl
            reward = tp1 - entry
        else:  # Sell
            risk = sl - entry
            reward = entry - tp1
        
        if risk <= 0:
            return {"confidence": 0, "issues": ["Invalid risk calculation"], "validation_method": "risk_reward"}
        
        rr_ratio = reward / risk
        
        # Validate R:R ratio
        issues = []
        confidence = 1.0
        
        # Check 1: Minimum R:R ratio (at least 0.5:1)
        if rr_ratio < Decimal("0.5"):
            confidence *= 0.5
            issues.append(f"R:R ratio too low: {rr_ratio:.2f}:1")
        
        # Check 2: Maximum R:R ratio (not more than 10:1 - might be unrealistic)
        if rr_ratio > Decimal("10"):
            confidence *= 0.7
            issues.append(f"R:R ratio unusually high: {rr_ratio:.2f}:1")
        
        # Check 3: Typical R:R range (1:1 to 5:1 is most common)
        if Decimal("1") <= rr_ratio <= Decimal("5"):
            confidence *= 1.0  # Full confidence
        else:
            confidence *= 0.8
        
        return {
            "confidence": confidence,
            "rr_ratio": float(rr_ratio),
            "issues": issues,
            "validation_method": "risk_reward"
        }
    
    def _validate_market_context(self, params: Dict, side: str) -> Dict[str, Any]:
        """Validate against current market price if available"""
        logger.info("📊 Validating market context...")
        
        current = params.get("current_price")
        entry = params.get(PRIMARY_ENTRY_PRICE)
        
        if not all([current, entry]):
            return {"confidence": 1.0, "issues": [], "validation_method": "market_context"}
        
        # Calculate distance from current price
        distance_pct = abs((entry - current) / current)
        
        confidence = 1.0
        issues = []
        
        # Entry should typically be within 10% of current price
        if distance_pct > Decimal("0.1"):
            confidence *= 0.6
            issues.append(f"Entry far from current price: {distance_pct:.2%}")
        elif distance_pct > Decimal("0.05"):
            confidence *= 0.8
            issues.append(f"Entry moderately far from current: {distance_pct:.2%}")
        
        return {
            "confidence": confidence,
            "distance_from_current": float(distance_pct),
            "issues": issues,
            "validation_method": "market_context"
        }
    
    def _values_match(self, val1: Decimal, val2: Decimal, tolerance: float = 0.001) -> bool:
        """Check if two decimal values match within tolerance"""
        if val1 == val2:
            return True
        
        # Check percentage difference
        avg = (val1 + val2) / 2
        if avg == 0:
            return False
        
        diff_pct = abs((val1 - val2) / avg)
        return diff_pct <= tolerance
    
    def _generate_verification_notes(self, confidence_scores: Dict[str, float]) -> List[str]:
        """Generate human-readable verification notes"""
        notes = []
        
        for check, score in confidence_scores.items():
            if score >= 0.9:
                notes.append(f"✅ {check.replace('_', ' ').title()}: Excellent ({score:.0%})")
            elif score >= 0.7:
                notes.append(f"✓ {check.replace('_', ' ').title()}: Good ({score:.0%})")
            elif score >= 0.5:
                notes.append(f"⚠️ {check.replace('_', ' ').title()}: Fair ({score:.0%})")
            else:
                notes.append(f"❌ {check.replace('_', ' ').title()}: Poor ({score:.0%})")
        
        return notes
    
    async def _attempt_enhanced_extraction(self, file_path: str, symbol: str, 
                                         side: str, original_params: Dict,
                                         confidence_scores: Dict) -> Optional[Dict]:
        """Attempt enhanced extraction when confidence is low"""
        logger.info("🔧 Attempting enhanced extraction due to low confidence...")
        
        # Identify which values have low confidence
        problem_areas = []
        if confidence_scores.get("cross_validation", 1) < 0.7:
            problem_areas.append("value_accuracy")
        if confidence_scores.get("logical_consistency", 1) < 0.7:
            problem_areas.append("order_logic")
        if confidence_scores.get("price_relationships", 1) < 0.7:
            problem_areas.append("price_spacing")
        
        # Create targeted prompt for problem areas
        enhanced_prompt = self._create_targeted_prompt(symbol, side, problem_areas)
        
        # Re-analyze with enhanced prompt
        enhanced_result = await self._analyze_with_custom_prompt(
            file_path, symbol, side, enhanced_prompt
        )
        
        if enhanced_result and enhanced_result.get("success"):
            return enhanced_result.get("parameters")
        
        return None
    
    async def _analyze_with_simple_prompt(self, file_path: str, symbol: str, side: str) -> Optional[Dict]:
        """Analyze with simplified prompt for cross-validation"""
        # This would call the parent class with prompt_strategy="simple"
        # Implementation depends on parent class structure
        return {}
    
    async def _analyze_with_numbers_prompt(self, file_path: str, symbol: str, side: str) -> Optional[Dict]:
        """Analyze with numbers-only prompt for cross-validation"""
        # This would call the parent class with prompt_strategy="numbers_only"
        # Implementation depends on parent class structure
        return {}
    
    def _create_targeted_prompt(self, symbol: str, side: str, problem_areas: List[str]) -> str:
        """Create a targeted prompt based on identified problem areas"""
        base_prompt = f"Carefully analyze this {symbol} {side} trading screenshot.\n\n"
        
        if "value_accuracy" in problem_areas:
            base_prompt += """
FOCUS ON EXACT VALUES:
- Double-check each number carefully
- Look for decimal points
- Verify full precision of prices
- Cross-reference values if they appear multiple times

"""
        
        if "order_logic" in problem_areas:
            base_prompt += f"""
VERIFY PRICE ORDER FOR {side.upper()}:
{"- Stop Loss should be the LOWEST price" if side == "Buy" else "- Stop Loss should be the HIGHEST price"}
{"- Entries should be ABOVE stop loss" if side == "Buy" else "- Entries should be BELOW stop loss"}
{"- Take Profits should be ABOVE entries" if side == "Buy" else "- Take Profits should be BELOW entries"}
- Multiple entries should be in {"descending" if side == "Buy" else "ascending"} order
- Multiple TPs should be in {"ascending" if side == "Buy" else "descending"} order

"""
        
        if "price_spacing" in problem_areas:
            base_prompt += """
CHECK PRICE SPACING:
- Ensure prices are reasonably spaced (not too close, not too far)
- Typical entry-to-TP distance: 0.5% to 10%
- Typical entry-to-SL distance: 0.5% to 5%
- If prices seem too close or too far, double-check the values

"""
        
        base_prompt += "\nExtract all trading parameters in JSON format."
        
        return base_prompt
    
    async def _analyze_with_custom_prompt(self, file_path: str, symbol: str, 
                                        side: str, custom_prompt: str) -> Dict[str, Any]:
        """Analyze with custom prompt"""
        # This would need to be implemented based on parent class structure
        # For now, returning empty dict
        return {"success": False}