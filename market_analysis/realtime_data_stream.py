#!/usr/bin/env python3
"""
Real-time Market Data Stream
WebSocket-based real-time data collection for enhanced market status updates
"""
import asyncio
import json
import logging
import time
import websockets
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class RealtimeTickerData:
    """Real-time ticker data from WebSocket"""
    symbol: str
    price: float
    price_change_24h: float
    price_change_pct_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float
    timestamp: datetime
    
class RealtimeDataStream:
    """WebSocket-based real-time market data stream for Bybit"""
    
    def __init__(self):
        self.ws_url = "wss://stream.bybit.com/v5/public/linear"
        self.subscribers = {}  # symbol -> list of callback functions
        self.connection = None
        self.running = False
        self.last_data = {}  # symbol -> RealtimeTickerData
        
        # Connection management
        self.reconnect_interval = 30  # seconds
        self.max_retries = 5
        self.retry_count = 0
        
    async def connect(self):
        """Establish WebSocket connection to Bybit"""
        try:
            logger.info("🔗 Connecting to Bybit WebSocket stream...")
            self.connection = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            self.running = True
            self.retry_count = 0
            logger.info("✅ Connected to Bybit WebSocket stream")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to WebSocket: {e}")
            self.running = False
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("🔌 Disconnected from Bybit WebSocket stream")
    
    async def subscribe_to_ticker(self, symbols: List[str]):
        """Subscribe to real-time ticker updates for specified symbols"""
        if not self.connection:
            logger.error("❌ Not connected to WebSocket")
            return False
        
        try:
            # Subscribe to ticker updates
            subscription_message = {
                "op": "subscribe",
                "args": [f"tickers.{symbol}" for symbol in symbols]
            }
            
            await self.connection.send(json.dumps(subscription_message))
            logger.info(f"📡 Subscribed to ticker updates for {len(symbols)} symbols: {', '.join(symbols)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to tickers: {e}")
            return False
    
    def add_ticker_callback(self, symbol: str, callback: Callable[[RealtimeTickerData], None]):
        """Add callback function for ticker updates"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = []
        self.subscribers[symbol].append(callback)
        logger.debug(f"✅ Added ticker callback for {symbol}")
    
    def get_latest_data(self, symbol: str) -> Optional[RealtimeTickerData]:
        """Get the latest ticker data for a symbol"""
        return self.last_data.get(symbol)
    
    async def start_listening(self):
        """Start listening for WebSocket messages"""
        if not self.connection:
            logger.error("❌ Cannot start listening - not connected")
            return
        
        logger.info("👂 Starting to listen for WebSocket messages...")
        
        try:
            async for message in self.connection:
                if not self.running:
                    break
                
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                    
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse WebSocket message: {e}")
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 WebSocket connection closed")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Error in WebSocket listener: {e}")
            self.running = False
    
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        try:
            # Check if this is a ticker update
            if data.get("topic", "").startswith("tickers."):
                ticker_data = data.get("data", {})
                if ticker_data:
                    symbol = ticker_data.get("symbol")
                    if symbol:
                        # Create RealtimeTickerData object
                        realtime_data = RealtimeTickerData(
                            symbol=symbol,
                            price=float(ticker_data.get("lastPrice", 0)),
                            price_change_24h=float(ticker_data.get("price24hPcnt", 0)) * 100,
                            price_change_pct_24h=float(ticker_data.get("price24hPcnt", 0)) * 100,
                            volume_24h=float(ticker_data.get("volume24h", 0)),
                            high_24h=float(ticker_data.get("highPrice24h", 0)),
                            low_24h=float(ticker_data.get("lowPrice24h", 0)),
                            timestamp=datetime.now()
                        )
                        
                        # Store latest data
                        self.last_data[symbol] = realtime_data
                        
                        # Call subscribers
                        if symbol in self.subscribers:
                            for callback in self.subscribers[symbol]:
                                try:
                                    callback(realtime_data)
                                except Exception as e:
                                    logger.error(f"Error in ticker callback for {symbol}: {e}")
            
            elif data.get("op") == "subscribe":
                # Subscription confirmation
                if data.get("success"):
                    logger.info(f"✅ Subscription confirmed: {data.get('ret_msg', 'Success')}")
                else:
                    logger.error(f"❌ Subscription failed: {data.get('ret_msg', 'Unknown error')}")
                    
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    async def run_with_reconnect(self, symbols: List[str]):
        """Run WebSocket connection with automatic reconnection"""
        while self.retry_count < self.max_retries:
            try:
                if await self.connect():
                    if await self.subscribe_to_ticker(symbols):
                        await self.start_listening()
                
                if not self.running and self.retry_count < self.max_retries:
                    self.retry_count += 1
                    logger.info(f"🔄 Reconnecting in {self.reconnect_interval}s (attempt {self.retry_count}/{self.max_retries})")
                    await asyncio.sleep(self.reconnect_interval)
                else:
                    break
                    
            except Exception as e:
                logger.error(f"❌ Error in WebSocket run loop: {e}")
                self.retry_count += 1
                if self.retry_count < self.max_retries:
                    await asyncio.sleep(self.reconnect_interval)
                else:
                    break
        
        logger.error(f"❌ Maximum retry attempts ({self.max_retries}) reached, stopping WebSocket")

# Global instance
realtime_stream = RealtimeDataStream()

# Helper function to start real-time data stream
async def start_realtime_stream(symbols: List[str] = None):
    """Start real-time data stream for specified symbols"""
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # Default symbols
    
    logger.info(f"🚀 Starting real-time data stream for {len(symbols)} symbols")
    
    # Run the stream in the background
    asyncio.create_task(realtime_stream.run_with_reconnect(symbols))
    
    # Give it a moment to establish connection
    await asyncio.sleep(2)
    
    return realtime_stream

# Helper function to get real-time price
def get_realtime_price(symbol: str) -> Optional[float]:
    """Get real-time price for a symbol if available"""
    data = realtime_stream.get_latest_data(symbol)
    return data.price if data else None