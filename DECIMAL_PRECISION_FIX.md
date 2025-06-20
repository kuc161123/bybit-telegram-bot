# Decimal Precision Fix for Screenshot Extraction

## Issue
Values extracted from screenshots were being rounded to 2 decimal places instead of preserving the full precision shown in the screenshots. For example, if a screenshot showed 0.78721, it was being stored as 0.78 instead.

## Root Cause
The `_auto_correct_params` method in `utils/ggshot_validator.py` was rounding all price values to 2 decimal places:

```python
# Round all prices to reasonable precision
for key in corrected:
    if "price" in key and corrected[key]:
        price = self._safe_decimal(corrected[key])
        if price > 0:
            # Round to 2 decimal places for most assets
            corrected[key] = round(price, 2)
```

## Solution Applied

### 1. Fixed ggshot_validator.py
Removed the rounding logic from `_auto_correct_params` to preserve full decimal precision:

```python
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
```

## Data Flow Verification

### 1. Screenshot Analysis (utils/screenshot_analyzer.py)
- The AI is instructed to preserve all decimal places (line 383-390)
- Values are stored as Decimal objects with full precision
- No rounding occurs during extraction

### 2. Parameter Validation (utils/ggshot_validator.py)
- Previously rounded to 2 decimal places (FIXED)
- Now preserves full precision from extraction

### 3. Storage in Chat Data (handlers/conversation.py)
- Line 615: `context.chat_data.update(extracted_data["parameters"])`
- Stores the exact Decimal values from extraction

### 4. Order Placement (execution/trader.py)
- Uses `value_adjusted_to_step` to adjust prices to exchange requirements
- This happens ONLY when placing orders, not during extraction/storage

## Exchange Precision Handling

When orders are placed, prices are adjusted to the symbol's tick_size:
- This is fetched from Bybit when the symbol is validated (conversation.py line 256)
- The adjustment happens in `utils/helpers.py` using `value_adjusted_to_step()`
- This ensures orders comply with exchange requirements while preserving maximum precision during extraction

## Testing Recommendations

1. Test with a screenshot containing precise decimal values (e.g., 0.78721)
2. Verify the extracted value matches exactly what's shown in the screenshot
3. Confirm the value is displayed with full precision in the confirmation message
4. Check that orders are placed with appropriate tick_size adjustment

## Summary

The fix ensures that:
1. ✅ Full decimal precision is extracted from screenshots
2. ✅ No premature rounding occurs during validation
3. ✅ Values are stored with exact precision in chat data
4. ✅ Rounding to tick_size happens only when placing orders on Bybit

This maintains accuracy throughout the screenshot analysis process while ensuring compliance with exchange requirements at order placement time.