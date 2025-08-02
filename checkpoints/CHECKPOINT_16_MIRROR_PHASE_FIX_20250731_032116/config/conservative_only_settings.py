#!/usr/bin/env python3
"""
Conservative-only trading enforcement settings
This file ensures only conservative approach is used throughout the system
"""

# Trading approach enforcement
ENFORCE_CONSERVATIVE_ONLY = True
ALLOWED_APPROACHES = ["conservative"]
DEFAULT_APPROACH = "conservative"

# Conservative approach specific settings
CONSERVATIVE_ENTRY_ORDERS = 4  # Number of limit orders for entry
CONSERVATIVE_TP_PERCENTAGES = [85, 5, 5, 5]  # TP distribution
CONSERVATIVE_FIRST_ENTRY_AS_MARKET = True  # First "limit" order executes as market

# Disable other approaches
DISABLE_FAST_APPROACH = True
DISABLE_GGSHOT_APPROACH = True

# Validation function
def validate_approach(approach: str) -> str:
    """Validate and enforce conservative approach"""
    if ENFORCE_CONSERVATIVE_ONLY:
        if approach.lower() not in ["conservative", "cons"]:
            return "conservative"
    return approach.lower()

# Export validation
def is_approach_allowed(approach: str) -> bool:
    """Check if approach is allowed"""
    return approach.lower() in ALLOWED_APPROACHES
