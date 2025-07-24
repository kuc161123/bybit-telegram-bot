import asyncio
from clients.bybit_client import bybit_client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_jtousdt():
    try:
        # Get JTOUSDT position
        pos_response = bybit_client.get_positions(category="linear", symbol="JTOUSDT")
        positions = pos_response.get("result", {}).get("list", [])
        
        # Get JTOUSDT orders
        order_response = bybit_client.get_open_orders(category="linear", symbol="JTOUSDT")
        orders = order_response.get("result", {}).get("list", [])
        
        print("JTOUSDT DETAILED ANALYSIS:")
        print("="*80)
        
        if positions:
            pos = positions[0]
            print(f"Position: {pos['size']} @ {pos['avgPrice']} ({pos['side']})")
            print(f"P&L: ${float(pos['unrealisedPnl']):.2f}")
            print(f"\nAll Orders ({len(orders)}):")
            
            for order in orders:
                print(f"\n  Order ID: {order.get('orderId', '')[:8]}...")
                print(f"  Link ID: {order.get('orderLinkId', '')}")
                print(f"  Type: {order.get('orderType')}")
                print(f"  Side: {order.get('side')}")
                print(f"  Price: {order.get('price')}")
                print(f"  Trigger Price: {order.get('triggerPrice', 'N/A')}")
                print(f"  Qty: {order.get('qty')}")
                print(f"  Reduce Only: {order.get('reduceOnly', False)}")
                print(f"  Stop Order Type: {order.get('stopOrderType', 'N/A')}")
                print(f"  Status: {order.get('orderStatus')}")
                
                # Check if this is the problematic order
                if order.get('price') == '0' and order.get('orderType') == 'Market':
                    print(f"  ⚠️ This is a Market order with price $0 - likely a TP/SL order")
                    
    except Exception as e:
        logger.error(f"Error checking JTOUSDT: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_jtousdt())