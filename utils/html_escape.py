#!/usr/bin/env python3
"""
HTML escaping utilities for Telegram messages
"""
import html
from typing import Optional, Union, List


def escape_html(text: Union[str, int, float, None]) -> str:
    """
    Safely escape text for use in Telegram HTML messages

    Args:
        text: Text to escape (can be string, number, or None)

    Returns:
        Escaped string safe for HTML parsing
    """
    if text is None:
        return ""

    # Convert numbers to string
    if isinstance(text, (int, float)):
        text = str(text)

    # Escape HTML special characters
    return html.escape(text)


def escape_list(items: List[Union[str, int, float]]) -> List[str]:
    """
    Escape a list of items for HTML

    Args:
        items: List of items to escape

    Returns:
        List of escaped strings
    """
    return [escape_html(item) for item in items]


def format_escaped(template: str, **kwargs) -> str:
    """
    Format a string template with escaped values

    Args:
        template: String template with placeholders
        **kwargs: Values to escape and insert

    Returns:
        Formatted string with escaped values
    """
    escaped_values = {key: escape_html(value) for key, value in kwargs.items()}
    return template.format(**escaped_values)