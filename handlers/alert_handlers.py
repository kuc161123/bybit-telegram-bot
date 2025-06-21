#!/usr/bin/env python3
"""
Alert system command and callback handlers
"""
import logging
from typing import Dict, List
from decimal import Decimal
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from alerts import AlertManager, AlertType, AlertPriority, Alert
from alerts.alert_types import ALERT_CONFIGS

logger = logging.getLogger(__name__)

# Alert type categories for UI
ALERT_CATEGORIES = {
    "Price Alerts": [
        AlertType.PRICE_ABOVE,
        AlertType.PRICE_BELOW,
        AlertType.PRICE_CROSS,
        AlertType.PRICE_CHANGE_PERCENT
    ],
    "Position Alerts": [
        AlertType.POSITION_PROFIT_AMOUNT,
        AlertType.POSITION_PROFIT_PERCENT,
        AlertType.POSITION_LOSS_AMOUNT,
        AlertType.POSITION_LOSS_PERCENT,
        AlertType.POSITION_BREAKEVEN,
        AlertType.POSITION_NEAR_TP,
        AlertType.POSITION_NEAR_SL
    ],
    "Risk Alerts": [
        AlertType.HIGH_LEVERAGE,
        AlertType.LARGE_POSITION,
        AlertType.ACCOUNT_DRAWDOWN,
        AlertType.CORRELATED_POSITIONS
    ],
    "Market Alerts": [
        AlertType.VOLATILITY_SPIKE,
        AlertType.VOLUME_SPIKE,
        AlertType.FUNDING_RATE
    ]
}

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /alerts command"""
    chat_id = update.effective_chat.id
    # Get alert manager from application attribute
    alert_manager: AlertManager = getattr(context.application, '_alert_manager', None)
    
    if not alert_manager:
        await update.message.reply_text("❌ Alert system not available")
        return
    
    # Show main alerts menu
    keyboard = [
        [InlineKeyboardButton("📊 My Alerts", callback_data="alerts_list")],
        [InlineKeyboardButton("➕ Create Alert", callback_data="alerts_create")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="alerts_settings")],
        [InlineKeyboardButton("📈 Alert History", callback_data="alerts_history")],
        [InlineKeyboardButton("❌ Close", callback_data="alerts_close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = """
🔔 <b>ALERT MANAGEMENT</b>
━━━━━━━━━━━━━━━

Monitor markets 24/7 with custom alerts:
• Price movements & targets
• Position P&L thresholds
• Risk warnings
• Market volatility

Select an option:
"""
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def handle_alerts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle alert system callbacks"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    # Get alert manager from application attribute
    alert_manager: AlertManager = getattr(context.application, '_alert_manager', None)
    
    if not alert_manager:
        await query.edit_message_text("❌ Alert system not available")
        return
    
    data = query.data
    
    # Main menu options
    if data == "alerts_list":
        await show_alerts_list(query, alert_manager, chat_id)
    
    elif data == "alerts_create":
        await show_alert_categories(query)
    
    elif data == "alerts_settings":
        await show_alert_settings(query, alert_manager, chat_id)
    
    elif data == "alerts_history":
        await show_alert_history(query, alert_manager, chat_id)
    
    elif data == "alerts_close":
        await query.delete_message()
    
    # Category selection
    elif data.startswith("alert_cat_"):
        category = data.replace("alert_cat_", "")
        await show_alert_types(query, category)
    
    # Alert type selection
    elif data.startswith("alert_type_"):
        alert_type_str = data.replace("alert_type_", "")
        alert_type = AlertType(alert_type_str)
        context.user_data['creating_alert_type'] = alert_type
        await prompt_alert_params(query, alert_type)
    
    # Alert actions
    elif data.startswith("alert_toggle_"):
        alert_id = data.replace("alert_toggle_", "")
        await toggle_alert(query, alert_manager, alert_id)
    
    elif data.startswith("alert_delete_"):
        alert_id = data.replace("alert_delete_", "")
        await delete_alert(query, alert_manager, alert_id)
    
    # Settings actions
    elif data.startswith("alert_pref_"):
        pref = data.replace("alert_pref_", "")
        await handle_preference_update(query, alert_manager, chat_id, pref)
    
    # Navigation
    elif data == "alerts_back":
        await show_main_menu(query)

async def show_alerts_list(query, alert_manager: AlertManager, chat_id: int):
    """Show user's alerts"""
    alerts = alert_manager.get_user_alerts(chat_id)
    
    if not alerts:
        keyboard = [
            [InlineKeyboardButton("➕ Create Alert", callback_data="alerts_create")],
            [InlineKeyboardButton("⬅️ Back", callback_data="alerts_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📭 You don't have any alerts yet.\n\nCreate your first alert to start monitoring!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return
    
    # Group alerts by type
    alerts_by_category = {}
    for category, types in ALERT_CATEGORIES.items():
        category_alerts = [a for a in alerts if a.type in types]
        if category_alerts:
            alerts_by_category[category] = category_alerts
    
    message = f"🔔 <b>YOUR ALERTS</b> ({len(alerts)} active)\n━━━━━━━━━━━━━━━\n\n"
    
    for category, category_alerts in alerts_by_category.items():
        message += f"<b>{category}</b>\n"
        for alert in category_alerts[:5]:  # Show max 5 per category
            status = "✅" if alert.enabled else "⏸"
            config = ALERT_CONFIGS.get(alert.type, {})
            emoji = config.get('emoji', '🔔')
            
            alert_desc = f"{emoji} {alert.type.value}"
            if alert.symbol:
                alert_desc += f" - {alert.symbol}"
            if alert.condition_value:
                alert_desc += f" @ {alert.condition_value}"
            
            message += f"{status} {alert_desc}\n"
        
        if len(category_alerts) > 5:
            message += f"   ... and {len(category_alerts) - 5} more\n"
        message += "\n"
    
    # Show management buttons for first few alerts
    keyboard = []
    for alert in alerts[:3]:
        action = "Disable" if alert.enabled else "Enable"
        keyboard.append([
            InlineKeyboardButton(
                f"{action} {alert.type.value[:20]}",
                callback_data=f"alert_toggle_{alert.id}"
            ),
            InlineKeyboardButton(
                "🗑 Delete",
                callback_data=f"alert_delete_{alert.id}"
            )
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Create New", callback_data="alerts_create")],
        [InlineKeyboardButton("⬅️ Back", callback_data="alerts_back")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_alert_categories(query):
    """Show alert categories for creation"""
    keyboard = []
    
    for category in ALERT_CATEGORIES.keys():
        keyboard.append([
            InlineKeyboardButton(
                category,
                callback_data=f"alert_cat_{category.replace(' ', '_')}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="alerts_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = """
➕ <b>CREATE NEW ALERT</b>
━━━━━━━━━━━━━━━

Select alert category:
"""
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_alert_types(query, category: str):
    """Show alert types in category"""
    category_name = category.replace('_', ' ')
    alert_types = ALERT_CATEGORIES.get(category_name, [])
    
    if not alert_types:
        await query.edit_message_text("❌ Invalid category")
        return
    
    keyboard = []
    
    for alert_type in alert_types:
        config = ALERT_CONFIGS.get(alert_type, {})
        emoji = config.get('emoji', '🔔')
        desc = config.get('description', alert_type.value)
        
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {desc}",
                callback_data=f"alert_type_{alert_type.value}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="alerts_create")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"""
➕ <b>CREATE {category_name.upper()}</b>
━━━━━━━━━━━━━━━

Select alert type:
"""
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def prompt_alert_params(query, alert_type: AlertType):
    """Prompt for alert parameters"""
    config = ALERT_CONFIGS.get(alert_type, {})
    
    message = f"""
⚙️ <b>CONFIGURE ALERT</b>
━━━━━━━━━━━━━━━

Type: {config.get('description', alert_type.value)}
{config.get('emoji', '🔔')} {config.get('help', '')}

"""
    
    # Add specific instructions based on alert type
    if 'symbol' in config.get('requires', []):
        message += "📊 Reply with: SYMBOL VALUE\n"
        message += "Example: BTCUSDT 50000\n"
    elif 'value' in config.get('requires', []):
        message += "📊 Reply with: VALUE\n"
        if 'percent' in alert_type.value:
            message += "Example: 10 (for 10%)\n"
        elif 'amount' in alert_type.value:
            message += "Example: 100 (for $100)\n"
        else:
            message += "Example: 50\n"
    
    message += "\nType /cancel to cancel"
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="alerts_create")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_alert_settings(query, alert_manager: AlertManager, chat_id: int):
    """Show alert settings"""
    prefs = alert_manager.storage.get_user_preferences(chat_id)
    
    # Format current settings
    daily_report = "✅ Enabled" if prefs.get('daily_report_enabled', True) else "❌ Disabled"
    report_time = prefs.get('daily_report_time', '08:00')
    min_priority = prefs.get('min_priority', 'low').upper()
    
    mute_start = prefs.get('mute_start')
    mute_end = prefs.get('mute_end')
    mute_status = f"{mute_start}:00 - {mute_end}:00" if mute_start and mute_end else "Not set"
    
    message = f"""
⚙️ <b>ALERT SETTINGS</b>
━━━━━━━━━━━━━━━

<b>Daily Report:</b> {daily_report}
<b>Report Time:</b> {report_time} UTC
<b>Min Priority:</b> {min_priority}
<b>Quiet Hours:</b> {mute_status}
"""
    
    keyboard = [
        [InlineKeyboardButton(
            "📊 Toggle Daily Report",
            callback_data="alert_pref_daily_toggle"
        )],
        [InlineKeyboardButton(
            "⏰ Change Report Time",
            callback_data="alert_pref_report_time"
        )],
        [InlineKeyboardButton(
            "🔔 Change Min Priority",
            callback_data="alert_pref_priority"
        )],
        [InlineKeyboardButton(
            "🔇 Set Quiet Hours",
            callback_data="alert_pref_quiet_hours"
        )],
        [InlineKeyboardButton("⬅️ Back", callback_data="alerts_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_alert_history(query, alert_manager: AlertManager, chat_id: int):
    """Show alert history"""
    history = alert_manager.storage.get_user_history(chat_id, limit=10)
    
    if not history:
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="alerts_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📭 No alert history yet.",
            reply_markup=reply_markup
        )
        return
    
    message = "📈 <b>RECENT ALERTS</b>\n━━━━━━━━━━━━━━━\n\n"
    
    for entry in history[-10:]:  # Show last 10
        triggered_at = entry['triggered_at']
        info = entry['info']
        alert = info.get('alert')
        
        if alert:
            config = ALERT_CONFIGS.get(alert.type, {})
            emoji = config.get('emoji', '🔔')
            
            time_str = triggered_at.strftime('%m/%d %H:%M')
            alert_desc = f"{emoji} {alert.type.value}"
            if alert.symbol:
                alert_desc += f" - {alert.symbol}"
            
            message += f"{time_str} | {alert_desc}\n"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="alerts_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def toggle_alert(query, alert_manager: AlertManager, alert_id: str):
    """Toggle alert enabled/disabled"""
    success = alert_manager.toggle_alert(alert_id)
    
    if success:
        await query.answer("✅ Alert updated")
        # Refresh the alerts list
        chat_id = query.message.chat_id
        await show_alerts_list(query, alert_manager, chat_id)
    else:
        await query.answer("❌ Failed to update alert")

async def delete_alert(query, alert_manager: AlertManager, alert_id: str):
    """Delete an alert"""
    success = alert_manager.delete_alert(alert_id)
    
    if success:
        await query.answer("✅ Alert deleted")
        # Refresh the alerts list
        chat_id = query.message.chat_id
        await show_alerts_list(query, alert_manager, chat_id)
    else:
        await query.answer("❌ Failed to delete alert")

async def handle_preference_update(query, alert_manager: AlertManager, 
                                 chat_id: int, pref: str):
    """Handle preference updates"""
    if pref == "daily_toggle":
        current = alert_manager.storage.get_user_preferences(chat_id).get('daily_report_enabled', True)
        alert_manager.update_preferences(chat_id, daily_report_enabled=not current)
        await query.answer("✅ Daily report toggled")
        await show_alert_settings(query, alert_manager, chat_id)
    
    elif pref == "priority":
        # Show priority options
        keyboard = [
            [InlineKeyboardButton("🟢 Low", callback_data="set_priority_low")],
            [InlineKeyboardButton("🟡 Medium", callback_data="set_priority_medium")],
            [InlineKeyboardButton("🔴 High", callback_data="set_priority_high")],
            [InlineKeyboardButton("⬅️ Back", callback_data="alerts_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select minimum alert priority:",
            reply_markup=reply_markup
        )
    
    # Add more preference handlers as needed

async def show_main_menu(query):
    """Show main alerts menu"""
    keyboard = [
        [InlineKeyboardButton("📊 My Alerts", callback_data="alerts_list")],
        [InlineKeyboardButton("➕ Create Alert", callback_data="alerts_create")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="alerts_settings")],
        [InlineKeyboardButton("📈 Alert History", callback_data="alerts_history")],
        [InlineKeyboardButton("❌ Close", callback_data="alerts_close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = """
🔔 <b>ALERT MANAGEMENT</b>
━━━━━━━━━━━━━━━

Monitor markets 24/7 with custom alerts:
• Price movements & targets
• Position P&L thresholds
• Risk warnings
• Market volatility

Select an option:
"""
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def handle_alert_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for alert creation"""
    if 'creating_alert_type' not in context.user_data:
        return
    
    chat_id = update.effective_chat.id
    # Get alert manager from application attribute
    alert_manager: AlertManager = getattr(context.application, '_alert_manager', None)
    alert_type = context.user_data['creating_alert_type']
    
    text = update.message.text.strip()
    parts = text.split()
    
    config = ALERT_CONFIGS.get(alert_type, {})
    requires = config.get('requires', [])
    
    try:
        if 'symbol' in requires and 'value' in requires:
            if len(parts) != 2:
                await update.message.reply_text("❌ Please provide: SYMBOL VALUE")
                return
            
            symbol = parts[0].upper()
            value = Decimal(parts[1])
            
            alert = alert_manager.create_alert(
                chat_id=chat_id,
                alert_type=alert_type,
                symbol=symbol,
                condition_value=value
            )
        
        elif 'value' in requires:
            if len(parts) != 1:
                await update.message.reply_text("❌ Please provide a single value")
                return
            
            value = Decimal(parts[0])
            
            alert = alert_manager.create_alert(
                chat_id=chat_id,
                alert_type=alert_type,
                condition_value=value
            )
        
        else:
            alert = alert_manager.create_alert(
                chat_id=chat_id,
                alert_type=alert_type
            )
        
        if alert:
            await update.message.reply_text(
                f"✅ Alert created successfully!\n\n"
                f"Type: {alert.type.value}\n"
                f"ID: {alert.id}\n\n"
                f"Use /alerts to manage your alerts."
            )
        else:
            await update.message.reply_text("❌ Failed to create alert")
        
        # Clear context
        del context.user_data['creating_alert_type']
        
    except ValueError:
        await update.message.reply_text("❌ Invalid value. Please enter a number.")
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        await update.message.reply_text("❌ Error creating alert")

async def test_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /testreport command - generates and sends a daily report immediately"""
    chat_id = update.effective_chat.id
    # Get alert manager from application attribute
    alert_manager: AlertManager = getattr(context.application, '_alert_manager', None)
    
    if not alert_manager:
        await update.message.reply_text("❌ Alert system not available")
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text("📊 Generating your daily report...")
    
    try:
        # Generate the report
        report = await alert_manager.report_generator.generate_report(chat_id)
        
        if report:
            # Delete processing message
            await processing_msg.delete()
            
            # Send the report
            await update.message.reply_text(
                report,
                parse_mode=ParseMode.HTML
            )
            
            # Also show how to configure daily reports
            config_msg = """
💡 <b>Daily Report Configuration</b>

This is a sample of your daily trading report.

To configure automatic daily reports:
• Use /alerts → ⚙️ Settings
• Toggle daily reports ON/OFF
• Set your preferred delivery time
• Default time: 08:00 UTC

Your reports will include:
• Account balance summary
• Trading performance metrics
• Open positions overview
• Win/loss statistics
• Trading tips
"""
            await update.message.reply_text(
                config_msg,
                parse_mode=ParseMode.HTML
            )
        else:
            await processing_msg.edit_text("📊 No trading data available for report generation.")
            
    except Exception as e:
        logger.error(f"Error generating test report: {e}")
        await processing_msg.edit_text("❌ Error generating report. Please try again later.")

def get_alert_conversation_handler():
    """Get conversation handler for alert creation"""
    return ConversationHandler(
        entry_points=[],  # Entry is handled by callbacks
        states={
            ALERT_WAITING_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_alert_text_input)
            ]
        },
        fallbacks=[
            MessageHandler(filters.COMMAND, lambda u, c: ConversationHandler.END)
        ],
        per_chat=True,
        per_user=True,
        per_message=False
    )