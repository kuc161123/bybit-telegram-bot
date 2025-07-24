#!/usr/bin/env python3
"""
Safe formatting utilities for Telegram HTML messages
Ensures all dynamic content is properly escaped
"""
import html
from typing import Any, Dict, Union
import re


def safe_format(template: str, **kwargs) -> str:
    """
    Safely format a string template with HTML-escaped values

    This function ensures all interpolated values are properly escaped
    to prevent HTML parsing errors in Telegram messages.

    Args:
        template: String template with {key} placeholders
        **kwargs: Values to interpolate (will be HTML-escaped)

    Returns:
        Formatted string with all values properly escaped
    """
    # Escape all values
    escaped_values = {}
    for key, value in kwargs.items():
        if value is None:
            escaped_values[key] = ""
        elif isinstance(value, (int, float)):
            # Format numbers but escape any special characters
            escaped_values[key] = html.escape(str(value))
        else:
            escaped_values[key] = html.escape(str(value))

    # Format the template
    return template.format(**escaped_values)


def escape_all_tags(text: str) -> str:
    """
    Escape all HTML-like tags in a string, preserving only allowed Telegram HTML

    Args:
        text: Text that may contain HTML-like content

    Returns:
        Text with all angle brackets escaped except allowed Telegram tags
    """
    # List of allowed Telegram HTML tags
    allowed_tags = ['b', 'i', 'u', 's', 'strike', 'code', 'pre', 'a', 'strong', 'em']

    # First, escape < and > (do NOT escape & yet)
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # Then restore allowed tags
    for tag in allowed_tags:
        # Opening tags
        text = text.replace(f'&lt;{tag}&gt;', f'<{tag}>')
        # Closing tags
        text = text.replace(f'&lt;/{tag}&gt;', f'</{tag}>')
        # Tags with attributes (like <a href="">)
        text = re.sub(f'&lt;{tag}([^&]*)&gt;', f'<{tag}\\1>', text)

    # Finally, escape & to prevent double-escaping
    text = text.replace('&', '&amp;')
    # But restore valid HTML entities
    text = text.replace('&amp;lt;', '&lt;')
    text = text.replace('&amp;gt;', '&gt;')
    text = text.replace('&amp;amp;', '&amp;')

    return text


def sanitize_for_telegram(text: str) -> str:
    """
    Final sanitization pass for Telegram HTML messages

    This catches any remaining problematic content that might cause parsing errors.

    Args:
        text: Complete message text

    Returns:
        Sanitized text safe for Telegram HTML parsing
    """
    # Remove any null bytes
    text = text.replace('\x00', '')

    # Ensure proper UTF-8 encoding
    text = text.encode('utf-8', errors='ignore').decode('utf-8')

    # Check for unmatched tags
    # Count opening and closing tags
    for tag in ['b', 'i', 'u', 's', 'code', 'pre', 'strong', 'em']:
        open_count = text.count(f'<{tag}>')
        close_count = text.count(f'</{tag}>')

        # If unmatched, escape all instances of this tag
        if open_count != close_count:
            text = text.replace(f'<{tag}>', f'&lt;{tag}&gt;')
            text = text.replace(f'</{tag}>', f'&lt;/{tag}&gt;')

    return text