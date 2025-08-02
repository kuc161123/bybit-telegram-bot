#!/usr/bin/env python3
"""
Telegram bot helper utilities
"""
import logging
from typing import Optional, Union
from telegram import Update, CallbackQuery
from telegram.error import BadRequest

logger = logging.getLogger(__name__)


async def safe_answer_callback(query: CallbackQuery, text: Optional[str] = None, show_alert: bool = False,
                             url: Optional[str] = None, cache_time: int = 0) -> bool:
    """
    Safely answer a callback query, handling timeout errors gracefully.

    Args:
        query: The callback query to answer
        text: Optional text to show to the user
        show_alert: Whether to show an alert dialog
        url: Optional URL to open
        cache_time: The time in seconds the result can be cached

    Returns:
        bool: True if successful, False if timeout or error
    """
    try:
        await query.answer(text=text, show_alert=show_alert, url=url, cache_time=cache_time)
        return True
    except BadRequest as e:
        # Handle the specific timeout error
        if "Query is too old" in str(e) or "query is too old" in str(e).lower():
            # This is expected when callbacks take time to process
            logger.debug(f"Callback query timeout (expected): {query.data}")
            return False
        else:
            # Other BadRequest errors should be logged
            logger.error(f"BadRequest error answering callback {query.data}: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error answering callback {query.data}: {e}")
        return False


async def safe_edit_message(query: CallbackQuery, text: str, parse_mode: Optional[str] = None,
                          reply_markup: Optional[object] = None, disable_web_page_preview: bool = None) -> bool:
    """
    Safely edit a message from a callback query, handling common errors.

    Args:
        query: The callback query with the message to edit
        text: New text for the message
        parse_mode: Optional parse mode (HTML, Markdown, etc.)
        reply_markup: Optional new inline keyboard
        disable_web_page_preview: Whether to disable link previews

    Returns:
        bool: True if successful, False if error
    """
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
        return True
    except BadRequest as e:
        error_str = str(e).lower()
        if "message is not modified" in error_str:
            # This happens when trying to edit with the same content
            logger.debug(f"Message not modified (same content): {query.data}")
            return True
        elif "message to edit not found" in error_str:
            # Message was deleted or is too old
            logger.warning(f"Message to edit not found: {query.data}")
            return False
        elif "query is too old" in error_str:
            # Callback timeout
            logger.debug(f"Callback timeout while editing: {query.data}")
            return False
        else:
            logger.error(f"BadRequest error editing message: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error editing message: {e}")
        return False


def extract_callback_data(callback_data: str, separator: str = ":") -> list:
    """
    Extract data from callback string.

    Args:
        callback_data: The callback data string
        separator: The separator used in the callback data

    Returns:
        list: List of extracted data parts
    """
    return callback_data.split(separator)


def build_callback_data(action: str, *args, separator: str = ":") -> str:
    """
    Build callback data string from components.

    Args:
        action: The action identifier
        *args: Additional arguments to include
        separator: The separator to use

    Returns:
        str: The formatted callback data string
    """
    parts = [action] + [str(arg) for arg in args]
    return separator.join(parts)