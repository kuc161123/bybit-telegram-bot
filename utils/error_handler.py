#!/usr/bin/env python3
"""
Enhanced error handling utilities for the trading bot
Provides consistent error handling and logging across the application
"""
import logging
import traceback
from functools import wraps
from typing import Any, Callable, Optional, Type, Union
from telegram.error import TelegramError
from pybit.exceptions import InvalidRequestError, FailedRequestError

logger = logging.getLogger(__name__)

class TradingBotError(Exception):
    """Base exception for trading bot errors"""
    pass

class PositionError(TradingBotError):
    """Errors related to position management"""
    pass

class OrderError(TradingBotError):
    """Errors related to order management"""
    pass

class ConfigurationError(TradingBotError):
    """Errors related to configuration"""
    pass

def handle_errors(
    default_return: Any = None,
    log_level: int = logging.ERROR,
    raise_on_error: bool = False,
    error_message: str = "An error occurred"
):
    """
    Decorator for consistent error handling
    
    Args:
        default_return: Value to return on error
        log_level: Logging level for errors
        raise_on_error: Whether to re-raise the exception
        error_message: Custom error message prefix
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    f"{error_message} in {func.__name__}: {str(e)}",
                    exc_info=True,
                    extra={
                        'function': func.__name__,
                        'module': func.__module__,
                        'error_type': type(e).__name__
                    }
                )
                if raise_on_error:
                    raise
                return default_return
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    f"{error_message} in {func.__name__}: {str(e)}",
                    exc_info=True,
                    extra={
                        'function': func.__name__,
                        'module': func.__module__,
                        'error_type': type(e).__name__
                    }
                )
                if raise_on_error:
                    raise
                return default_return
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def categorize_error(error: Exception) -> tuple[str, int, bool]:
    """
    Categorize errors for appropriate handling
    
    Returns:
        tuple: (category, severity, is_recoverable)
        - category: Error category string
        - severity: 1-5 (1=debug, 5=critical)
        - is_recoverable: Whether the error is recoverable
    """
    error_map = {
        # Telegram errors
        TelegramError: ("telegram", 3, True),
        
        # Bybit errors
        InvalidRequestError: ("bybit_request", 3, True),
        FailedRequestError: ("bybit_failed", 4, True),
        
        # Python errors
        ValueError: ("validation", 2, True),
        KeyError: ("data_access", 2, True),
        ConnectionError: ("connection", 4, True),
        TimeoutError: ("timeout", 3, True),
        
        # Custom errors
        PositionError: ("position", 3, True),
        OrderError: ("order", 4, False),
        ConfigurationError: ("config", 5, False),
    }
    
    for error_type, (category, severity, recoverable) in error_map.items():
        if isinstance(error, error_type):
            return category, severity, recoverable
    
    return "unknown", 4, False

async def safe_execute(
    func: Callable,
    *args,
    context: Optional[dict] = None,
    max_retries: int = 3,
    **kwargs
) -> tuple[bool, Any, Optional[str]]:
    """
    Safely execute a function with retry logic
    
    Returns:
        tuple: (success, result, error_message)
    """
    last_error = None
    context = context or {}
    
    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return True, result, None
            
        except Exception as e:
            last_error = e
            category, severity, is_recoverable = categorize_error(e)
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {str(e)}",
                extra={
                    'attempt': attempt + 1,
                    'max_retries': max_retries,
                    'error_category': category,
                    'severity': severity,
                    'context': context
                }
            )
            
            if not is_recoverable or attempt == max_retries - 1:
                break
            
            # Exponential backoff
            await asyncio.sleep(2 ** attempt)
    
    error_msg = f"Failed after {max_retries} attempts: {str(last_error)}"
    logger.error(error_msg, exc_info=last_error)
    return False, None, error_msg

import asyncio

class ErrorContext:
    """Context manager for error tracking"""
    
    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.errors = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.errors.append({
                'type': exc_type.__name__,
                'message': str(exc_val),
                'traceback': traceback.format_exc()
            })
            logger.error(
                f"Error in {self.operation}",
                exc_info=True,
                extra={'context': self.context, 'errors': self.errors}
            )
        return False  # Don't suppress the exception