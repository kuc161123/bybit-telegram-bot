#!/usr/bin/env python3
"""
Shared state management and message handling.
"""
import asyncio
import time
import logging
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest, TimedOut as TelegramTimedOut, NetworkError as TelegramNetworkError
from config.settings import MAX_RETRIES, RETRY_DELAY
from utils.formatters import split_long_message

logger = logging.getLogger(__name__)

# --- Optimized Message Handling ---
class MessageManager:
    def __init__(self):
        self.pending_edits = {}
        self.edit_lock = asyncio.Lock()
        self.message_cache = {}
        self.cache_ttl = 60  # 1 minute
    
    async def smart_edit_message(self, ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                                message_id: Optional[int], text: str, 
                                reply_markup = None,
                                force_edit: bool = False):
        """Optimized message editing with deduplication and caching"""
        if not message_id:
            logger.warning(f"No msg_id to edit for chat {chat_id}")
            return await self.send_new_message(ctx, chat_id, text, reply_markup)
        
        # Check if this exact message is already being sent
        edit_key = f"{chat_id}_{message_id}"
        
        # Check cache to avoid redundant edits
        cache_key = f"{edit_key}_{hash(text)}"
        if cache_key in self.message_cache and not force_edit:
            cache_time, _ = self.message_cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return  # Skip redundant edit
        
        async with self.edit_lock:
            if edit_key in self.pending_edits and not force_edit:
                return  # Skip duplicate edit
            
            self.pending_edits[edit_key] = True
        
        try:
            await ctx.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=message_id, 
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=ParseMode.HTML
            )
            # Cache successful edit
            self.message_cache[cache_key] = (time.time(), text)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass  # Ignore unchanged message
            elif "message to edit not found" in str(e):
                return await self.send_new_message(ctx, chat_id, text, reply_markup)
            else:
                logger.error(f"BadRequest in smart_edit: {e}")
        except Exception as e:
            logger.error(f"Exception in smart_edit: {e}")
        finally:
            async with self.edit_lock:
                self.pending_edits.pop(edit_key, None)
    
    async def send_new_message(self, ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                              text: str, reply_markup = None):
        """Send new message with error handling and retry logic"""
        for attempt in range(MAX_RETRIES):
            try:
                return await ctx.bot.send_message(
                    chat_id=chat_id, 
                    text=text, 
                    reply_markup=reply_markup, 
                    parse_mode=ParseMode.HTML
                )
            except TelegramTimedOut:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"Failed to send message after {MAX_RETRIES} attempts")
                    return None
            except Exception as e:
                logger.error(f"Error sending new message: {e}")
                return None
    
    def cleanup_cache(self):
        """Clean up old cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (cache_time, _) in self.message_cache.items()
            if current_time - cache_time > self.cache_ttl
        ]
        for key in expired_keys:
            del self.message_cache[key]

# Global message manager
msg_manager = MessageManager()

async def send_long_message(bot, chat_id: int, message: str, parse_mode=None, reply_markup=None):
    """Send a potentially long message, splitting it if necessary"""
    message_parts = split_long_message(message)
    
    for i, part in enumerate(message_parts):
        try:
            # Only add reply_markup to the last message
            markup = reply_markup if i == len(message_parts) - 1 else None
            await bot.send_message(
                chat_id=chat_id,
                text=part,
                parse_mode=parse_mode,
                reply_markup=markup
            )
            # Small delay between messages to avoid rate limiting
            if i < len(message_parts) - 1:
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error sending message part {i+1}/{len(message_parts)}: {e}")
            # Continue with remaining parts even if one fails