# GGShot Streamlined Input Flow Implementation

## Overview
Implemented a streamlined input flow for GGShot approach that allows sequential input of limit orders and take profits without returning to menu after each value.

## Changes Made

### 1. New Conversation States
Added new states for the streamlined flow:
- `GGSHOT_LIMIT_FLOW_1`, `GGSHOT_LIMIT_FLOW_2`, `GGSHOT_LIMIT_FLOW_3` - For limit order sequential input
- `GGSHOT_TP_FLOW_1`, `GGSHOT_TP_FLOW_2`, `GGSHOT_TP_FLOW_3`, `GGSHOT_TP_FLOW_4` - For take profit sequential input

### 2. Modified Callbacks
- Changed `ggshot_edit_limits` callback to start `start_ggshot_limit_flow()` instead of showing menu
- Changed `ggshot_edit_tps` callback to start `start_ggshot_tp_flow()` instead of showing menu

### 3. New Handler Functions

#### Limit Order Flow:
- `start_ggshot_limit_flow()` - Initiates the limit order flow, prompts for Limit 1
- `handle_ggshot_limit_1_input()` - Processes Limit 1, prompts for Limit 2
- `handle_ggshot_limit_2_input()` - Processes Limit 2, prompts for Limit 3
- `handle_ggshot_limit_3_input()` - Processes Limit 3, shows confirmation

#### Take Profit Flow:
- `start_ggshot_tp_flow()` - Initiates the TP flow, prompts for TP1
- `handle_ggshot_tp_1_input()` - Processes TP1, prompts for TP2
- `handle_ggshot_tp_2_input()` - Processes TP2, prompts for TP3
- `handle_ggshot_tp_3_input()` - Processes TP3, prompts for TP4
- `handle_ggshot_tp_4_input()` - Processes TP4, shows confirmation

### 4. Navigation Features
- Back buttons at each step to go to previous input
- Cancel button to exit the flow
- Progress indication showing which value is being entered
- Shows previously entered values as you progress

### 5. Flow Example

#### Before (Old Flow):
1. Click "Change Limit Orders"
2. See menu with Limit 1, 2, 3 buttons
3. Click "Limit 1"
4. Enter value
5. Returns to menu
6. Click "Limit 2"
7. Enter value
8. Returns to menu
9. Click "Limit 3"
10. Enter value
11. Returns to menu
12. Click "Done"

#### After (New Streamlined Flow):
1. Click "Change Limit Orders"
2. Prompted for Limit 1 → Enter value
3. Automatically prompted for Limit 2 → Enter value
4. Automatically prompted for Limit 3 → Enter value
5. Shows confirmation with all values

## Benefits
1. **Faster Input**: Reduces clicks from ~12 to ~4 for entering all limit orders
2. **Better UX**: Natural flow without menu interruptions
3. **Clear Progress**: Users see which value they're entering and what's already entered
4. **Flexible Navigation**: Can go back to correct mistakes without starting over
5. **Mobile Friendly**: Less navigation, more efficient on mobile devices

## Testing
To test the new flow:
1. Start a GGShot trade setup
2. After screenshot analysis, click "Change Limit Orders"
3. Enter values sequentially when prompted
4. Use back buttons to test navigation
5. Verify all values are saved correctly

## Technical Notes
- Flow state is tracked in `chat_data` with keys like `ggshot_limit_flow_active`
- Each handler validates input and manages state transitions
- Back navigation preserves previously entered values
- Cancel at any point returns to the main edit screen