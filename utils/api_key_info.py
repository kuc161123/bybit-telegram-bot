#!/usr/bin/env python3
"""
API Key Information and Expiration Tracking
Provides functionality to check API key expiration dates for both main and mirror accounts
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from clients.bybit_client import bybit_client

logger = logging.getLogger(__name__)

async def get_api_key_expiration_info(account_type: str = "main") -> Dict:
    """
    Get API key expiration information for specified account
    
    Args:
        account_type: "main" or "mirror"
        
    Returns:
        Dict with expiration info including days remaining
    """
    try:
        # Select appropriate client
        if account_type == "mirror":
            try:
                from execution.mirror_trader import bybit_client_2, ENABLE_MIRROR_TRADING
                if not ENABLE_MIRROR_TRADING or not bybit_client_2:
                    return {
                        "error": "Mirror trading not enabled",
                        "days_remaining": None,
                        "expiry_date": None,
                        "status": "disabled"
                    }
                client = bybit_client_2
            except ImportError:
                return {
                    "error": "Mirror client not available",
                    "days_remaining": None,
                    "expiry_date": None,
                    "status": "error"
                }
        else:
            client = bybit_client
            
        if not client:
            return {
                "error": f"No {account_type} client configured",
                "days_remaining": None,
                "expiry_date": None,
                "status": "error"
            }
        
        # Get API key information from Bybit
        try:
            response = client.get_api_key_information()
            
            if response.get("retCode") == 0:
                result = response.get("result", {})
                
                # Extract expiration timestamp (could be milliseconds or ISO string)
                expired_at = result.get("expiredAt")
                
                if expired_at and expired_at != "0":
                    # Try to parse as ISO string first (mirror account format)
                    try:
                        if isinstance(expired_at, str) and 'T' in expired_at:
                            # ISO format: 2025-09-14T11:26:06Z
                            # Remove timezone info to make it naive like current_date
                            expiry_date = datetime.fromisoformat(expired_at.replace('Z', '+00:00')).replace(tzinfo=None)
                        else:
                            # Milliseconds format
                            expiry_date = datetime.fromtimestamp(int(expired_at) / 1000)
                    except:
                        # Fallback: try direct timestamp
                        expiry_date = datetime.fromtimestamp(int(expired_at) / 1000)
                    current_date = datetime.now()
                    
                    # Calculate days remaining
                    time_remaining = expiry_date - current_date
                    days_remaining = time_remaining.days
                    
                    # Determine status
                    if days_remaining < 0:
                        status = "expired"
                    elif days_remaining <= 7:
                        status = "critical"  # Less than a week
                    elif days_remaining <= 30:
                        status = "warning"   # Less than a month
                    else:
                        status = "healthy"
                    
                    return {
                        "days_remaining": days_remaining,
                        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "status": status,
                        "permissions": result.get("permissions", {}).get("PermissionList", []),
                        "vip_level": result.get("vipLevel", "0"),
                        "mkt_maker_level": result.get("mktMakerLevel", "0"),
                        "affiliate_id": result.get("affiliateID", 0),
                        "error": None
                    }
                else:
                    # No expiration set (permanent key)
                    return {
                        "days_remaining": "∞",
                        "expiry_date": "Never",
                        "status": "permanent",
                        "permissions": result.get("permissions", {}).get("PermissionList", []),
                        "vip_level": result.get("vipLevel", "0"),
                        "error": None
                    }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                logger.error(f"API key info request failed for {account_type}: {error_msg}")
                return {
                    "error": error_msg,
                    "days_remaining": None,
                    "expiry_date": None,
                    "status": "error"
                }
                
        except Exception as api_error:
            logger.error(f"Error calling API for {account_type}: {api_error}")
            return {
                "error": str(api_error),
                "days_remaining": None,
                "expiry_date": None,
                "status": "error"
            }
            
    except Exception as e:
        logger.error(f"Error getting API key info for {account_type}: {e}")
        return {
            "error": str(e),
            "days_remaining": None,
            "expiry_date": None,
            "status": "error"
        }

async def get_all_api_keys_status() -> Tuple[Dict, Dict]:
    """
    Get API key status for both main and mirror accounts
    
    Returns:
        Tuple of (main_info, mirror_info) dictionaries
    """
    main_info = await get_api_key_expiration_info("main")
    mirror_info = await get_api_key_expiration_info("mirror")
    
    return main_info, mirror_info

def format_api_key_status(info: Dict, account_type: str = "main") -> str:
    """
    Format API key status for display
    
    Args:
        info: API key information dictionary
        account_type: "main" or "mirror"
        
    Returns:
        Formatted string for display
    """
    account_label = "Main" if account_type == "main" else "Mirror"
    
    if info.get("status") == "error":
        return f"🔴 {account_label}: Error - {info.get('error', 'Unknown')}"
    elif info.get("status") == "disabled":
        return f"⚫ {account_label}: Disabled"
    elif info.get("status") == "permanent":
        return f"🟢 {account_label}: Permanent (No expiry)"
    elif info.get("status") == "expired":
        return f"🔴 {account_label}: EXPIRED ({info.get('expiry_date', 'Unknown')})"
    elif info.get("status") == "critical":
        days = info.get("days_remaining", 0)
        return f"🔴 {account_label}: {days} days left! (Expires: {info.get('expiry_date', 'Unknown')})"
    elif info.get("status") == "warning":
        days = info.get("days_remaining", 0)
        return f"🟡 {account_label}: {days} days left (Expires: {info.get('expiry_date', 'Unknown')})"
    else:  # healthy
        days = info.get("days_remaining", 0)
        return f"🟢 {account_label}: {days} days (Expires: {info.get('expiry_date', 'Unknown')})"

async def format_api_key_dashboard_section() -> str:
    """
    Format API key status section for dashboard (async version)
    
    Returns:
        Formatted string for dashboard display
    """
    try:
        # Get API key status for both accounts
        main_info, mirror_info = await get_all_api_keys_status()
        
        # Format the section
        section = "\n🔑 <b>API KEY STATUS</b>\n"
        section += "─" * 30 + "\n"
        
        # Main account
        main_status = format_api_key_status(main_info, "main")
        section += main_status + "\n"
        
        # Mirror account
        mirror_status = format_api_key_status(mirror_info, "mirror")
        section += mirror_status + "\n"
        
        # Add warning if any keys are expiring soon
        if main_info.get("status") in ["critical", "expired"] or mirror_info.get("status") in ["critical", "expired"]:
            section += "\n⚠️ <b>ACTION REQUIRED:</b> Renew API keys soon!\n"
        
        return section
        
    except Exception as e:
        logger.error(f"Error formatting API key dashboard section: {e}")
        return "\n🔑 <b>API KEY STATUS</b>\n─────────────\n⚪ Unable to check API key status\n"