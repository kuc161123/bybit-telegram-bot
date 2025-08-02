#!/usr/bin/env python3
"""
Enhanced position closure with mirror verification.
Ensures positions are closed on both accounts.
"""

async def close_position_with_mirror_verification(symbol: str, side: str, chat_data: dict):
    """Close position on both main and mirror accounts with verification."""

    from clients.bybit_helpers import get_position_info
    from execution.mirror_trader import bybit_client_2

    results = {'main': False, 'mirror': False, 'errors': []}

    try:
        # Close on main account
        main_result = await close_main_position(symbol, side)
        results['main'] = main_result.get('success', False)

        # Close on mirror account
        if bybit_client_2:
            mirror_result = await close_mirror_position(symbol, side)
            results['mirror'] = mirror_result.get('success', False)

            # Verify both are closed
            await asyncio.sleep(1)  # Wait for execution

            # Check main
            main_pos = await get_position_info(symbol)
            if main_pos and float(main_pos.get('size', 0)) > 0:
                results['errors'].append("Main position still open after closure attempt")

            # Check mirror
            if bybit_client_2:
                mirror_pos = await get_mirror_position_info(symbol)
                if mirror_pos and float(mirror_pos.get('size', 0)) > 0:
                    results['errors'].append("Mirror position still open after closure attempt")
                    # Retry mirror closure
                    await close_mirror_position(symbol, side)

    except Exception as e:
        results['errors'].append(str(e))

    return results
