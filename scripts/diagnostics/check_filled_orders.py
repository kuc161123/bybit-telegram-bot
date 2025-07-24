import asyncio
from clients.bybit_client import bybit_client
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_filled_orders():
    symbols = ['ENAUSDT', 'TIAUSDT', 'JTOUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'KAVAUSDT', 'BTCUSDT']
    
    try:
        # Get filled orders from history (last 24 hours)
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
        
        print("CHECKING FILLED ORDERS (Last 24 hours):")
        print("="*80)
        
        for symbol in symbols:
            # Get order history for this symbol
            response = bybit_client.get_order_history(
                category="linear",
                symbol=symbol,
                orderStatus="Filled",
                limit=50
            )
            
            if response and response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                
                # Filter for TP orders (reduceOnly + specific orderLinkId patterns)
                tp_orders = []
                for order in orders:
                    link_id = order.get("orderLinkId", "")
                    if order.get("reduceOnly") and ("FAST" in link_id or "TP" in link_id):
                        tp_orders.append(order)
                
                if tp_orders:
                    print(f"\n{symbol} - FILLED TP ORDERS:")
                    print("-"*40)
                    for order in tp_orders:
                        fill_time = datetime.fromtimestamp(int(order.get("updatedTime", 0)) / 1000)
                        print(f"Order ID: {order.get('orderId')[:8]}...")
                        print(f"Link ID: {order.get('orderLinkId')}")
                        print(f"Price: {order.get('price')} -> Filled: {order.get('avgPrice')}")
                        print(f"Qty: {order.get('qty')}")
                        print(f"Filled at: {fill_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"Status: {order.get('orderStatus')}")
                        print()
                        
    except Exception as e:
        logger.error(f"Error checking filled orders: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_filled_orders())