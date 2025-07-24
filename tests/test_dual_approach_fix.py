#!/usr/bin/env python3
"""
Test script to verify the dual-approach auto-rebalancer fixes
"""

import asyncio
import logging
from decimal import Decimal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_dual_approach_detection():
    """Test the dual-approach detection and verification"""
    
    print("🧪 Testing Dual-Approach Auto-Rebalancer Fixes")
    print("=" * 60)
    
    # Mock position data
    mock_position = {
        'symbol': 'JTOUSDT',
        'side': 'Buy',
        'size': '100.0',
        'positionIdx': 1
    }
    
    # Mock orders for dual-approach (1 Fast TP + 4 Conservative TPs + SL)
    mock_orders = [
        # Fast TP
        {
            'symbol': 'JTOUSDT',
            'side': 'Sell',  # Opposite of position side
            'orderLinkId': 'BOT_FAST_JTOUSDT_TP_12345',
            'qty': '30.0',
            'price': '2.100',
            'positionIdx': 1
        },
        # Conservative TPs
        {
            'symbol': 'JTOUSDT',
            'side': 'Sell',
            'orderLinkId': 'BOT_CONS_JTOUSDT_TP1_12345',
            'qty': '59.5',  # 85% of 70 (Conservative portion)
            'price': '2.080',
            'positionIdx': 1
        },
        {
            'symbol': 'JTOUSDT',
            'side': 'Sell',
            'orderLinkId': 'BOT_CONS_JTOUSDT_TP2_12345',
            'qty': '3.5',   # 5% of 70
            'price': '2.150',
            'positionIdx': 1
        },
        {
            'symbol': 'JTOUSDT',
            'side': 'Sell',
            'orderLinkId': 'BOT_CONS_JTOUSDT_TP3_12345',
            'qty': '3.5',   # 5% of 70
            'price': '2.200',
            'positionIdx': 1
        },
        {
            'symbol': 'JTOUSDT',
            'side': 'Sell',
            'orderLinkId': 'BOT_CONS_JTOUSDT_TP4_12345',
            'qty': '3.5',   # 5% of 70
            'price': '2.250',
            'positionIdx': 1
        },
        # SL
        {
            'symbol': 'JTOUSDT',
            'side': 'Buy',  # Same as position side
            'orderLinkId': 'BOT_CONS_JTOUSDT_SL_12345',
            'qty': '100.0',
            'triggerPrice': '1.800',
            'positionIdx': 1
        }
    ]
    
    print(f"📊 Mock Position: {mock_position['symbol']} {mock_position['side']} {mock_position['size']}")
    print(f"📋 Mock Orders: {len(mock_orders)} orders (5 TPs + 1 SL)")
    
    # Test the auto-rebalancer's position detection
    try:
        from execution.auto_rebalancer import AutoRebalancer
        
        rebalancer = AutoRebalancer()
        
        # Test position detection
        changes = await rebalancer._detect_position_changes([mock_position], mock_orders)
        
        print("\n🔍 Position Detection Results:")
        print(f"   Changes detected: {len(changes)}")
        
        for change in changes:
            approach = change.get('approach', 'Unknown')
            change_type = change.get('type', 'Unknown')
            print(f"   - {approach} approach: {change_type}")
        
        # Expected: Should detect both Fast and Conservative approaches separately
        fast_changes = [c for c in changes if c.get('approach') == 'Fast']
        conservative_changes = [c for c in changes if c.get('approach') == 'Conservative']
        
        print(f"\n✅ Fast approach changes: {len(fast_changes)}")
        print(f"✅ Conservative approach changes: {len(conservative_changes)}")
        
        if len(fast_changes) > 0 and len(conservative_changes) > 0:
            print("🎯 SUCCESS: Dual-approach detection working correctly!")
        else:
            print("❌ ISSUE: Dual-approach detection not working as expected")
            
    except Exception as e:
        print(f"❌ Error testing auto-rebalancer: {e}")
        logger.error(f"Auto-rebalancer test failed: {e}", exc_info=True)
    
    # Test the trade verifier with dual-approach
    try:
        from utils.trade_verifier import verify_position
        
        print("\n🔍 Testing Trade Verifier with Dual-Approach:")
        
        # Test Fast approach verification
        fast_orders = [o for o in mock_orders if 'FAST_' in o.get('orderLinkId', '')]
        result_fast = await verify_position('JTOUSDT', 'Buy', mock_position, fast_orders)
        
        print(f"   Fast verification: {'✅ PASSED' if result_fast.get('verified') else '⚠️ ISSUES'}")
        if not result_fast.get('verified'):
            for disc in result_fast.get('discrepancies', []):
                print(f"     - {disc.get('message', 'Unknown issue')}")
        
        # Test Conservative approach verification
        cons_orders = [o for o in mock_orders if any(p in o.get('orderLinkId', '') for p in ['CONS_', 'TP1_', 'TP2_', 'TP3_', 'TP4_'])]
        result_cons = await verify_position('JTOUSDT', 'Buy', mock_position, cons_orders)
        
        print(f"   Conservative verification: {'✅ PASSED' if result_cons.get('verified') else '⚠️ ISSUES'}")
        if not result_cons.get('verified'):
            for disc in result_cons.get('discrepancies', []):
                print(f"     - {disc.get('message', 'Unknown issue')}")
        
        # Test full position verification (should detect dual-approach)
        result_full = await verify_position('JTOUSDT', 'Buy', mock_position, mock_orders)
        
        print(f"   Full position verification: {'✅ PASSED' if result_full.get('verified') else 'ℹ️ DUAL-APPROACH'}")
        if not result_full.get('verified'):
            for disc in result_full.get('discrepancies', []):
                message = disc.get('message', 'Unknown issue')
                if 'dual-approach' in message.lower():
                    print(f"     ℹ️ {message}")
                else:
                    print(f"     - {message}")
                    
    except Exception as e:
        print(f"❌ Error testing trade verifier: {e}")
        logger.error(f"Trade verifier test failed: {e}", exc_info=True)
    
    print("\n🏁 Test completed!")
    

if __name__ == "__main__":
    asyncio.run(test_dual_approach_detection())