#!/usr/bin/env python3
"""
GGShot Screenshot Analysis Validator
Ensures robustness and validates extracted parameters for both long and short trades
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)

class GGShotValidator:
    """Validates extracted parameters from screenshot analysis"""

    def __init__(self):
        self.max_price_deviation = 0.5  # 50% max deviation from entry
        self.min_rr_ratio = 0.5  # Minimum risk/reward ratio
        self.max_leverage = 125  # Maximum allowed leverage

    async def validate_extracted_parameters(
        self,
        params: Dict[str, Any],
        symbol: str,
        side: str,
        current_market_price: Optional[Decimal] = None
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Comprehensive validation of extracted parameters

        Returns:
            (success, errors, validated_params)
        """
        errors = []
        validated_params = params.copy()

        # Step 1: Validate required parameters exist
        required_validation = self._validate_required_params(params, side)
        if not required_validation[0]:
            errors.extend(required_validation[1])
            return False, errors, {}

        # Step 2: Validate price direction logic
        direction_validation = self._validate_direction_logic(params, side)
        if not direction_validation[0]:
            errors.extend(direction_validation[1])

        # Step 3: Validate price reasonableness
        range_validation = self._validate_price_ranges(params, current_market_price)
        if not range_validation[0]:
            errors.extend(range_validation[1])

        # Step 4: Validate risk/reward ratios
        rr_validation = self._validate_risk_reward(params, side)
        if not rr_validation[0]:
            errors.extend(rr_validation[1])

        # Step 5: Validate leverage and margin
        leverage_validation = self._validate_leverage_margin(params)
        if not leverage_validation[0]:
            errors.extend(leverage_validation[1])

        # Step 6: Validate order sequence (for conservative)
        if self._is_conservative_strategy(params):
            sequence_validation = self._validate_order_sequence(params, side)
            if not sequence_validation[0]:
                errors.extend(sequence_validation[1])

        # Step 7: Auto-correct minor issues if possible
        if len(errors) == 0:
            validated_params = self._auto_correct_params(validated_params, side)

        success = len(errors) == 0
        return success, errors, validated_params

    def _validate_required_params(self, params: Dict, side: str) -> Tuple[bool, List[str]]:
        """Validate all required parameters are present"""
        errors = []

        # Check for entry price
        if not params.get("primary_entry_price"):
            errors.append("Missing primary entry price")

        # Check for at least TP1 and SL
        if not params.get("tp1_price"):
            errors.append("Missing take profit price (TP1)")
        if not params.get("sl_price"):
            errors.append("Missing stop loss price")

        return len(errors) == 0, errors

    def _validate_direction_logic(self, params: Dict, side: str) -> Tuple[bool, List[str]]:
        """Validate prices follow correct direction logic"""
        errors = []

        entry = self._safe_decimal(params.get("primary_entry_price", 0))
        sl = self._safe_decimal(params.get("sl_price", 0))

        if entry <= 0 or sl <= 0:
            return True, []  # Skip if prices invalid

        if side == "Buy":  # Long position
            # Validate TPs are above entry
            for i in range(1, 5):
                tp_key = f"tp{i}_price"
                if tp_key in params:
                    tp = self._safe_decimal(params[tp_key])
                    if tp > 0 and tp <= entry:
                        errors.append(f"TP{i} ({tp}) must be above entry ({entry}) for LONG trades")

            # Validate SL is below entry
            if sl >= entry:
                errors.append(f"Stop loss ({sl}) must be below entry ({entry}) for LONG trades")

            # Validate limit entries are below primary entry (for conservative)
            for i in range(1, 4):
                limit_key = f"limit_entry_{i}_price"
                if limit_key in params:
                    limit_price = self._safe_decimal(params[limit_key])
                    if limit_price > 0 and limit_price > entry:
                        errors.append(f"Limit entry {i} ({limit_price}) should be below primary entry ({entry}) for LONG trades")

        else:  # Short position
            # Validate TPs are below entry
            for i in range(1, 5):
                tp_key = f"tp{i}_price"
                if tp_key in params:
                    tp = self._safe_decimal(params[tp_key])
                    if tp > 0 and tp >= entry:
                        errors.append(f"TP{i} ({tp}) must be below entry ({entry}) for SHORT trades")

            # Validate SL is above entry
            if sl <= entry:
                errors.append(f"Stop loss ({sl}) must be above entry ({entry}) for SHORT trades")

            # Validate limit entries are above primary entry (for conservative)
            for i in range(1, 4):
                limit_key = f"limit_entry_{i}_price"
                if limit_key in params:
                    limit_price = self._safe_decimal(params[limit_key])
                    if limit_price > 0 and limit_price < entry:
                        errors.append(f"Limit entry {i} ({limit_price}) should be above primary entry ({entry}) for SHORT trades")

        return len(errors) == 0, errors

    def _validate_price_ranges(self, params: Dict, market_price: Optional[Decimal]) -> Tuple[bool, List[str]]:
        """Validate prices are within reasonable ranges"""
        errors = []

        entry = self._safe_decimal(params.get("primary_entry_price", 0))
        if entry <= 0:
            return True, []  # Skip if entry invalid

        # Check against market price if available
        if market_price and market_price > 0:
            deviation = abs(entry - market_price) / market_price
            if deviation > 0.1:  # More than 10% from market
                errors.append(f"Entry price ({entry}) is {deviation*100:.1f}% away from current market ({market_price})")

        # Check all prices are within reasonable range of entry
        all_prices = []
        for key, value in params.items():
            if "price" in key and value:
                price = self._safe_decimal(value)
                if price > 0:
                    all_prices.append((key, price))

        for price_key, price in all_prices:
            if price == entry:
                continue
            deviation = abs(price - entry) / entry
            if deviation > self.max_price_deviation:
                errors.append(f"{price_key} ({price}) is {deviation*100:.1f}% away from entry - seems unrealistic")

        return len(errors) == 0, errors

    def _validate_risk_reward(self, params: Dict, side: str) -> Tuple[bool, List[str]]:
        """Validate risk/reward ratios"""
        errors = []

        entry = self._safe_decimal(params.get("primary_entry_price", 0))
        tp1 = self._safe_decimal(params.get("tp1_price", 0))
        sl = self._safe_decimal(params.get("sl_price", 0))

        if entry <= 0 or tp1 <= 0 or sl <= 0:
            return True, []  # Skip if prices invalid

        if side == "Buy":
            risk = entry - sl
            reward = tp1 - entry
        else:
            risk = sl - entry
            reward = entry - tp1

        if risk <= 0:
            errors.append("Invalid risk calculation - check stop loss placement")
        elif reward <= 0:
            errors.append("Invalid reward calculation - check take profit placement")
        else:
            rr_ratio = reward / risk
            if rr_ratio < self.min_rr_ratio:
                errors.append(f"Risk/Reward ratio ({rr_ratio:.2f}) is below minimum ({self.min_rr_ratio})")

        return len(errors) == 0, errors

    def _validate_leverage_margin(self, params: Dict) -> Tuple[bool, List[str]]:
        """Validate leverage and margin parameters"""
        errors = []

        leverage = params.get("leverage", 10)
        margin = self._safe_decimal(params.get("margin_amount", 100))

        if leverage < 1 or leverage > self.max_leverage:
            errors.append(f"Leverage ({leverage}) must be between 1 and {self.max_leverage}")

        if margin < 10:
            errors.append(f"Margin amount ({margin}) is too small - minimum is 10 USDT")
        elif margin > 100000:
            errors.append(f"Margin amount ({margin}) seems unusually large - please verify")

        return len(errors) == 0, errors

    def _validate_order_sequence(self, params: Dict, side: str) -> Tuple[bool, List[str]]:
        """Validate order sequence for conservative strategy"""
        errors = []

        # Check TP sequence
        tp_prices = []
        for i in range(1, 5):
            tp_key = f"tp{i}_price"
            if tp_key in params:
                tp_prices.append((i, self._safe_decimal(params[tp_key])))

        if len(tp_prices) > 1:
            # Verify TPs are in correct sequence
            if side == "Buy":
                # TPs should be in ascending order
                for i in range(1, len(tp_prices)):
                    if tp_prices[i][1] <= tp_prices[i-1][1]:
                        errors.append(f"TP{tp_prices[i][0]} should be higher than TP{tp_prices[i-1][0]} for LONG trades")
            else:
                # TPs should be in descending order
                for i in range(1, len(tp_prices)):
                    if tp_prices[i][1] >= tp_prices[i-1][1]:
                        errors.append(f"TP{tp_prices[i][0]} should be lower than TP{tp_prices[i-1][0]} for SHORT trades")

        # Check limit order sequence
        limit_prices = []
        for i in range(1, 4):
            limit_key = f"limit_entry_{i}_price"
            if limit_key in params:
                limit_prices.append((i, self._safe_decimal(params[limit_key])))

        if len(limit_prices) > 1:
            # Verify limits are in correct sequence
            if side == "Buy":
                # Limits should be in descending order (buying lower)
                for i in range(1, len(limit_prices)):
                    if limit_prices[i][1] >= limit_prices[i-1][1]:
                        errors.append(f"Limit {limit_prices[i][0]} should be lower than Limit {limit_prices[i-1][0]} for LONG trades")
            else:
                # Limits should be in ascending order (selling higher)
                for i in range(1, len(limit_prices)):
                    if limit_prices[i][1] <= limit_prices[i-1][1]:
                        errors.append(f"Limit {limit_prices[i][0]} should be higher than Limit {limit_prices[i-1][0]} for SHORT trades")

        return len(errors) == 0, errors

    def _auto_correct_params(self, params: Dict, side: str) -> Dict:
        """Auto-correct minor parameter issues"""
        corrected = params.copy()

        # Ensure leverage is within bounds
        if "leverage" in corrected:
            corrected["leverage"] = max(1, min(self.max_leverage, int(corrected["leverage"])))

        # Ensure margin is reasonable
        if "margin_amount" in corrected:
            margin = self._safe_decimal(corrected["margin_amount"])
            if margin < 10:
                corrected["margin_amount"] = Decimal("10")
            elif margin > 100000:
                corrected["margin_amount"] = Decimal("100000")

        # PRESERVE FULL DECIMAL PRECISION - DO NOT ROUND PRICES HERE
        # Prices will be adjusted to tick_size only when placing orders
        # This ensures we keep the exact values from screenshots

        return corrected

    def _is_conservative_strategy(self, params: Dict) -> bool:
        """Check if this is a conservative strategy based on parameters"""
        # If we have multiple limit entries or multiple TPs, it's conservative
        has_multiple_limits = any(f"limit_entry_{i}_price" in params for i in range(1, 4))
        has_multiple_tps = sum(1 for i in range(1, 5) if f"tp{i}_price" in params) > 1
        return has_multiple_limits or has_multiple_tps

    def _safe_decimal(self, value: Any) -> Decimal:
        """Safely convert value to Decimal"""
        try:
            if value is None:
                return Decimal("0")
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def format_validation_report(self, errors: List[str], params: Dict, side: str) -> str:
        """Format a user-friendly validation report"""
        if not errors:
            return "✅ All parameters validated successfully!"

        report = "❌ <b>Validation Issues Found:</b>\n\n"

        # Group errors by type
        direction_errors = [e for e in errors if "must be above" in e or "must be below" in e]
        range_errors = [e for e in errors if "away from" in e or "unrealistic" in e]
        rr_errors = [e for e in errors if "Risk/Reward" in e]
        other_errors = [e for e in errors if e not in direction_errors + range_errors + rr_errors]

        if direction_errors:
            report += "🔄 <b>Direction Logic Issues:</b>\n"
            for error in direction_errors:
                report += f"  • {error}\n"
            report += "\n"

        if range_errors:
            report += "📏 <b>Price Range Issues:</b>\n"
            for error in range_errors:
                report += f"  • {error}\n"
            report += "\n"

        if rr_errors:
            report += "⚖️ <b>Risk/Reward Issues:</b>\n"
            for error in rr_errors:
                report += f"  • {error}\n"
            report += "\n"

        if other_errors:
            report += "⚠️ <b>Other Issues:</b>\n"
            for error in other_errors:
                report += f"  • {error}\n"
            report += "\n"

        # Add helpful guidance
        direction = "LONG" if side == "Buy" else "SHORT"
        report += f"💡 <b>Tips for {direction} trades:</b>\n"
        if side == "Buy":
            report += "  • Take profits should be ABOVE entry price\n"
            report += "  • Stop loss should be BELOW entry price\n"
            report += "  • Limit orders should be BELOW current price\n"
        else:
            report += "  • Take profits should be BELOW entry price\n"
            report += "  • Stop loss should be ABOVE entry price\n"
            report += "  • Limit orders should be ABOVE current price\n"

        return report

# Global validator instance
ggshot_validator = GGShotValidator()

async def validate_ggshot_parameters(
    params: Dict[str, Any],
    symbol: str,
    side: str,
    current_price: Optional[Decimal] = None
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Convenience function to validate GGShot parameters

    Returns:
        (success, errors, validated_params)
    """
    return await ggshot_validator.validate_extracted_parameters(params, symbol, side, current_price)