#!/usr/bin/env python3
"""
Update trader.py to pass account_type when setting up TP/SL orders
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 60)
    logger.info("UPDATING TRADER.PY FOR ACCOUNT-AWARE MONITORS")
    logger.info("=" * 60)
    
    with open('execution/trader.py', 'r') as f:
        content = f.read()
    
    # Update all setup_tp_sl_orders calls to include account_type
    replacements = [
        # Fast approach
        ('''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=tp_sl_qty,
                    entry_price=avg_price,
                    tp_prices=[tp_price],  # Single TP for fast approach
                    tp_percentages=[100],
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="FAST",
                    qty_step=qty_step,
                    initial_position_size=tp_sl_qty
                )''',
         '''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=tp_sl_qty,
                    entry_price=avg_price,
                    tp_prices=[tp_price],  # Single TP for fast approach
                    tp_percentages=[100],
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="FAST",
                    qty_step=qty_step,
                    initial_position_size=tp_sl_qty,
                    account_type="main"  # Main account trading
                )'''),
        
        # Conservative approach
        ('''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=final_sl_qty,  # Target position size
                    entry_price=avg_limit_price,
                    tp_prices=tp_prices[:4],  # Use first 4 TP prices
                    tp_percentages=[85, 5, 5, 5],  # Conservative TP distribution
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="CONSERVATIVE",
                    qty_step=qty_step,
                    initial_position_size=initial_position_size  # Initial position from first order
                )''',
         '''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=final_sl_qty,  # Target position size
                    entry_price=avg_limit_price,
                    tp_prices=tp_prices[:4],  # Use first 4 TP prices
                    tp_percentages=[85, 5, 5, 5],  # Conservative TP distribution
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="CONSERVATIVE",
                    qty_step=qty_step,
                    initial_position_size=initial_position_size,  # Initial position from first order
                    account_type="main"  # Main account trading
                )'''),
        
        # GGShot fast
        ('''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=qty,
                    entry_price=avg_price,
                    tp_prices=[tp_price] if tp_price else [],
                    tp_percentages=[100],
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="FAST",
                    qty_step=qty_step,
                    initial_position_size=qty
                )''',
         '''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=qty,
                    entry_price=avg_price,
                    tp_prices=[tp_price] if tp_price else [],
                    tp_percentages=[100],
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="FAST",
                    qty_step=qty_step,
                    initial_position_size=qty,
                    account_type="main"  # Main account trading
                )'''),
        
        # GGShot conservative
        ('''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=final_sl_qty,  # Target position size
                    entry_price=avg_entry,
                    tp_prices=tp_prices[:4],  # Use AI-extracted TP prices
                    tp_percentages=[85, 5, 5, 5],  # Conservative TP distribution
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="CONSERVATIVE",
                    qty_step=qty_step,
                    initial_position_size=initial_qty  # Initial position size
                )''',
         '''enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=final_sl_qty,  # Target position size
                    entry_price=avg_entry,
                    tp_prices=tp_prices[:4],  # Use AI-extracted TP prices
                    tp_percentages=[85, 5, 5, 5],  # Conservative TP distribution
                    sl_price=sl_price,
                    chat_id=update.effective_chat.id,
                    approach="CONSERVATIVE",
                    qty_step=qty_step,
                    initial_position_size=initial_qty,  # Initial position size
                    account_type="main"  # Main account trading
                )''')
    ]
    
    # Apply replacements
    changes_made = 0
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            changes_made += 1
            logger.info(f"✅ Updated setup_tp_sl_orders call #{changes_made}")
        else:
            # Try without exact whitespace matching
            old_compressed = ' '.join(old.split())
            content_compressed = ' '.join(content.split())
            if old_compressed in content_compressed:
                logger.warning(f"⚠️ Found compressed match for replacement #{changes_made + 1}")
    
    if changes_made > 0:
        with open('execution/trader.py', 'w') as f:
            f.write(content)
        logger.info(f"\n✅ Updated {changes_made} setup_tp_sl_orders calls")
    else:
        logger.warning("⚠️ Could not find exact matches. Applying general fix...")
        
        # General fix - add account_type to all setup_tp_sl_orders calls
        content = content.replace(
            'initial_position_size=tp_sl_qty\n                )',
            'initial_position_size=tp_sl_qty,\n                    account_type="main"  # Main account trading\n                )'
        )
        content = content.replace(
            'initial_position_size=initial_position_size  # Initial position from first order\n                )',
            'initial_position_size=initial_position_size,  # Initial position from first order\n                    account_type="main"  # Main account trading\n                )'
        )
        content = content.replace(
            'initial_position_size=qty\n                )',
            'initial_position_size=qty,\n                    account_type="main"  # Main account trading\n                )'
        )
        content = content.replace(
            'initial_position_size=initial_qty  # Initial position size\n                )',
            'initial_position_size=initial_qty,  # Initial position size\n                    account_type="main"  # Main account trading\n                )'
        )
        
        with open('execution/trader.py', 'w') as f:
            f.write(content)
        logger.info("✅ Applied general fix to add account_type parameter")
    
    # Also check mirror_trader.py if it exists
    logger.info("\n📝 Checking mirror_trader.py...")
    try:
        with open('execution/mirror_trader.py', 'r') as f:
            mirror_content = f.read()
        
        if 'setup_tp_sl_orders' in mirror_content:
            # Update mirror trader calls to use account_type="mirror"
            mirror_content = mirror_content.replace(
                'account_type="main"',
                'account_type="mirror"'
            )
            
            # Add account_type if missing
            if 'account_type=' not in mirror_content and 'setup_tp_sl_orders' in mirror_content:
                logger.warning("⚠️ mirror_trader.py needs account_type='mirror' added to setup_tp_sl_orders calls")
            
            with open('execution/mirror_trader.py', 'w') as f:
                f.write(mirror_content)
            logger.info("✅ Updated mirror_trader.py to use account_type='mirror'")
    except FileNotFoundError:
        logger.info("   mirror_trader.py not found (this is OK)")
    
    logger.info("\n🎯 TRADER UPDATE COMPLETE!")
    logger.info("All new positions will now create monitors with account-aware keys")

if __name__ == "__main__":
    main()