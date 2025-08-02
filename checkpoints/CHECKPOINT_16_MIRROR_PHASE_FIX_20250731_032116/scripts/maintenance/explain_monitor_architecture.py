#!/usr/bin/env python3
"""
Deep explanation of how monitors work for main vs mirror accounts
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

logger.info("""
============================================================
ENHANCED TP/SL MONITOR ARCHITECTURE EXPLANATION
============================================================

CURRENT DESIGN: SEPARATE MONITORS PER ACCOUNT
--------------------------------------------

The Enhanced TP/SL Manager uses SEPARATE monitors for main and mirror accounts,
NOT a single monitor watching both. Here's why and how:

1. MONITOR KEY FORMAT:
   - Both use: {SYMBOL}_{SIDE} (e.g., "XRPUSDT_Buy")
   - This creates potential for key collision!
   - Solution: The system differentiates by the 'account_type' field

2. CURRENT STRUCTURE (7 total monitors):
   - 1 main account monitor: DOGEUSDT_Buy (account_type='main')
   - 6 mirror account monitors: (all with account_type='mirror')
     * ICPUSDT_Sell
     * IDUSDT_Sell  
     * JUPUSDT_Sell
     * TIAUSDT_Buy
     * LINKUSDT_Buy
     * XRPUSDT_Buy

3. HOW IT WORKS:
   
   Main Account Monitor:
   ---------------------
   monitor_key = "DOGEUSDT_Buy"
   monitor_data = {
       'symbol': 'DOGEUSDT',
       'side': 'Buy',
       'account_type': 'main',    # <-- This determines which client
       'chat_id': 5634913742,     # <-- Alerts enabled
       'has_mirror': True         # <-- Indicates mirror position exists
   }
   
   When monitor_and_adjust_orders() runs:
   - Uses bybit_client (main account) for API calls
   - Sends alerts to Telegram (chat_id present)
   - Can trigger mirror sync operations
   
   Mirror Account Monitor:
   ----------------------
   monitor_key = "XRPUSDT_Buy"
   monitor_data = {
       'symbol': 'XRPUSDT',
       'side': 'Buy', 
       'account_type': 'mirror',  # <-- This determines which client
       'chat_id': None,           # <-- No alerts
       'has_mirror': False        # <-- Mirror positions don't have mirrors
   }
   
   When monitor_and_adjust_orders() runs:
   - Uses bybit_client_2 (mirror account) for API calls
   - Does NOT send alerts (chat_id is None)
   - All operations happen silently

4. LIMITATION OF CURRENT DESIGN:
   
   If you have XRPUSDT Buy on BOTH accounts:
   - Main: monitor_key = "XRPUSDT_Buy" 
   - Mirror: monitor_key = "XRPUSDT_Buy"
   - COLLISION! Only one can exist in the dictionary
   
   This is why currently the bot doesn't have the same position
   on both accounts (except during brief sync periods).

5. THE MONITORING LOOP:
   
   Every 5 seconds:
   ```python
   for monitor_key, monitor_data in position_monitors.items():
       if monitor_data['account_type'] == 'mirror':
           # Use mirror client (bybit_client_2)
           # No alerts sent
       else:
           # Use main client (bybit_client)  
           # Alerts sent to Telegram
       
       await monitor_and_adjust_orders(symbol, side)
   ```

6. WHY SEPARATE MONITORS?
   
   Advantages:
   - Independent TP/SL levels per account
   - Different position sizes handled correctly
   - Can disable alerts for mirror only
   - Allows different entry prices
   
   Disadvantages:
   - Can't have same symbol/side on both accounts
   - More memory usage (2x monitors)
   - Requires careful key management

7. ALTERNATIVE DESIGN (NOT IMPLEMENTED):
   
   Single monitor watching both:
   monitor_key = "XRPUSDT_Buy"
   monitor_data = {
       'main_position': {...},
       'mirror_position': {...}
   }
   
   This would be more complex but allow same positions
   on both accounts.

SUMMARY:
--------
- Each account has its OWN monitor (7 total = 1 main + 6 mirror)
- Monitors are differentiated by 'account_type' field
- Mirror monitors have chat_id=None to disable alerts
- The monitoring loop checks each monitor independently
- This is why you can't have XRPUSDT_Buy on BOTH accounts
  (the keys would collide)
""")

# Show current reality
logger.info("\nCURRENT MONITORING REALITY:")
logger.info("-" * 50)
logger.info("When the bot logs 'Monitoring 7 positions':")
logger.info("  - It's checking 7 SEPARATE monitors")
logger.info("  - 1 for main account (DOGEUSDT)")
logger.info("  - 6 for mirror account")
logger.info("  - Each monitor watches ONE position on ONE account")
logger.info("  - NOT one monitor watching both accounts")