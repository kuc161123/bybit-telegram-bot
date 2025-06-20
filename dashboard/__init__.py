"""Analytics Dashboard package for the trading bot."""

from .generator_analytics_compact import build_mobile_dashboard_text, build_analytics_dashboard_text
from .keyboards_analytics import build_enhanced_dashboard_keyboard, build_analytics_dashboard_keyboard

# Alias for compatibility
build_dashboard_text_async = build_mobile_dashboard_text