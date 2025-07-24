# Dashboard Silent Refresh Fix

## Problem
The dashboard was sending notifications every 30 seconds during auto-refresh, which was disturbing users with constant notification sounds/vibrations.

## Root Cause
The auto-refresh mechanism in `handlers/commands.py` was:
1. Trying to edit the existing message
2. If edit failed (even for minor reasons), it would fall back to sending a new message
3. New messages always trigger notifications in Telegram

## Solution Implemented

### 1. **Smart Edit Handling**
- When auto-refresh tries to edit a message and fails, we now check WHY it failed
- If the content is unchanged ("message is not modified"), we skip the update entirely
- Only send a new message if the original was actually deleted

### 2. **Content Hash Checking**
- Added MD5 hash comparison of dashboard content
- For auto-refresh, if content hasn't changed, skip the update completely
- This prevents unnecessary API calls and potential notifications

### 3. **Silent Notifications**
- When auto-refresh must send a new message (e.g., original was deleted), it now uses `disable_notification=True`
- Manual refreshes (button clicks) still send notifications for user feedback

## Code Changes

### In `_send_or_edit_dashboard_message()`:

1. **Added content hash checking:**
```python
# Calculate content hash for comparison (only for auto-refresh)
if not new_msg:
    content_hash = hashlib.md5(dashboard_text.encode()).hexdigest()
    last_content_hash = ctx.chat_data.get('last_dashboard_content_hash')
    
    if content_hash == last_content_hash:
        # Content hasn't changed, skip update
        logger.debug("Dashboard content unchanged, skipping auto-refresh")
        ctx.chat_data['last_dashboard_refresh'] = time.time()
        return
```

2. **Improved edit error handling:**
```python
except Exception as e:
    # For auto-refresh, check the type of error
    error_str = str(e).lower()
    if "message is not modified" in error_str or "message to edit not found" not in error_str:
        # Message content is identical or minor error - just update refresh time
        logger.debug(f"Dashboard unchanged or minor error: {e}")
        ctx.chat_data['last_dashboard_refresh'] = time.time()
        return  # Don't send a new message for unchanged content
```

3. **Silent message sending for auto-refresh:**
```python
# Auto-refresh where message was deleted - send new without notification
sent = await ctx.bot.send_message(
    c_id, 
    dashboard_text, 
    parse_mode=ParseMode.HTML,
    reply_markup=keyboard,
    disable_notification=True  # Silent update for auto-refresh
)
```

## Benefits

1. **No More Notification Spam**: Auto-refresh happens silently in the background
2. **Reduced API Calls**: Skips updates when content hasn't changed
3. **Better User Experience**: Dashboard stays updated without disturbing the user
4. **Manual Control**: Manual refresh button still provides feedback with notifications

## How It Works Now

### Auto-Refresh (every 30 seconds):
- ✅ If content unchanged → Skip update
- ✅ If content changed → Edit existing message (no notification)
- ✅ If message deleted → Send new message silently

### Manual Refresh (button click):
- ✅ Always deletes old and sends new
- ✅ Shows notification for user feedback
- ✅ Ensures user knows refresh happened

## Testing

To verify the fix is working:
1. Open the dashboard with active positions
2. Leave it open for a few minutes
3. You should see the dashboard update without any notifications
4. Click the refresh button manually - this should show a notification

## Technical Details

- Uses MD5 hashing for content comparison (fast and sufficient for this use case)
- Stores `last_dashboard_content_hash` in chat_data
- Distinguishes between auto-refresh (`new_msg=False`) and manual refresh (`new_msg=True`)
- Handles all edge cases (deleted messages, identical content, network errors)