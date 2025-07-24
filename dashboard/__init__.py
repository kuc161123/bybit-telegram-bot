"""Analytics Dashboard package for the trading bot."""

# Import new v2 components
from .generator_v2 import build_mobile_dashboard_text, dashboard_generator
from .keyboards_v2 import DashboardKeyboards

# Keep legacy imports for backward compatibility
from .generator_analytics_compact import (
    build_mobile_dashboard_text as build_mobile_dashboard_text_legacy,
    build_analytics_dashboard_text
)
from .keyboards_analytics import (
    build_enhanced_dashboard_keyboard as build_enhanced_dashboard_keyboard_legacy,
    build_analytics_dashboard_keyboard
)

# Alias for compatibility
build_dashboard_text_async = build_mobile_dashboard_text
build_enhanced_dashboard_keyboard = lambda c, ctx, p, m: DashboardKeyboards.main_dashboard(p > 0, False)