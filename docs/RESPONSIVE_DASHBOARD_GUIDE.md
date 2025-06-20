# Responsive Dashboard Guide

The Bybit Trading Bot now features a **responsive dashboard** that automatically adapts to different device screen sizes, providing optimal viewing experience across all devices.

## Overview

The responsive dashboard system detects your device type and adjusts:
- Box widths and padding
- Information density
- Feature visibility
- Text truncation
- Number of positions shown

## Device Size Options

### 1. Small Phone (`small`)
- **Width**: 28 characters
- **Best for**: Older phones, compact screens
- **Features**: Ultra-compact layout, essential info only
- **Positions shown**: 3 maximum

### 2. Standard Phone (`medium`) - Default
- **Width**: 32 characters  
- **Best for**: Most smartphones (iPhone 12/13/14)
- **Features**: Balanced layout with key features
- **Positions shown**: 4 maximum

### 3. Large Phone (`large`)
- **Width**: 36 characters
- **Best for**: Pro Max/Plus models, large phones
- **Features**: Enhanced layout with extended info
- **Positions shown**: 5 maximum

### 4. Tablet/Desktop (`tablet`)
- **Width**: 40 characters
- **Best for**: iPads, tablets, desktop clients
- **Features**: Full layout with all features
- **Positions shown**: 8 maximum

## How to Set Your Device Size

### Method 1: Command
```
/device
```
This opens an interactive menu where you can select your device type.

### Method 2: Auto-Detection
By default, the bot uses the "medium" layout which works well for most phones. Select "Auto-Detect" to use this default.

## Visual Examples

### Small Phone Layout
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   💎 BYBIT TERMINAL 💎
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─ 💰 ACCOUNT ──────────────┐
│ Total: $10,000.00         │
│ Available: $8,500.00      │
└───────────────────────────┘

━━━ 💎 P&L Scenarios ━━━
🎯 TP1: +$125.50
🏆 All: +$350.00
💀 SL: -$150.00
```

### Large Phone Layout
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   💎 BYBIT TERMINAL 💎
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─ 💰 ACCOUNT ──────────────────────┐
│ Total: $10,000.00                 │
│ Available: $8,500.00              │
│ In Use: $1,500.00                 │
└───────────────────────────────────┘

┌───────────────────────────────────┐
│ 💎 P&L MATRIX                     │
├───────────────────────────────────┤
│ 🎯 TP1 Hit: +$125.50              │
│ 🏆 All TPs: +$350.00              │
│ 💀 All SLs: -$150.00              │
│ ⚖️ R:R = 1:2.3 ✅                  │
└───────────────────────────────────┘
```

## Responsive Features

### 1. Dynamic Box Sizing
- Boxes automatically adjust width based on device
- Padding scales appropriately
- Border styles remain consistent

### 2. Smart Text Truncation
- Labels truncate with "…" when too long
- Values are preserved in full when possible
- Critical information is prioritized

### 3. Adaptive Information Display
- Small devices show essential data only
- Larger devices get extended statistics
- Performance metrics appear on tablets/desktop

### 4. Position Card Scaling
- Compact cards on small screens
- Full detail cards on larger screens
- Number of positions shown varies by device

## Best Practices

1. **Choose the Right Size**: Select the option that matches your primary device
2. **Test Different Sizes**: Try different settings to find your preference
3. **Save Battery**: Smaller layouts use less data and battery
4. **Readability First**: Choose a size that's comfortable to read

## Troubleshooting

### Dashboard looks cramped
- Try selecting a larger device size
- Use `/device` command to change

### Too much scrolling required
- Select a smaller device size for more compact view
- Reduces vertical space usage

### Information missing
- Larger device sizes show more details
- Essential info is always visible

## Technical Details

The responsive system uses a configuration class that adjusts:
```python
- box_width: Character width of boxes
- padding: Internal spacing
- max_label_width: Maximum label length
- show_extended_info: Toggle for extra details
- max_positions_shown: Position display limit
- compact_mode: Ultra-compact formatting
```

## Future Enhancements

- Auto-detection based on Telegram client
- Custom width settings
- Orientation detection
- Theme preferences
- Font size considerations

---

**Note**: The responsive dashboard ensures optimal viewing regardless of your device. Set it once and enjoy a perfectly formatted trading terminal!