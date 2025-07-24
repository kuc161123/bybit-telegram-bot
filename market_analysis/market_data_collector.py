#!/usr/bin/env python3
"""
Market Data Collector
Real-time market data collection from Bybit API for accurate market status
"""
import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from clients.bybit_client import bybit_client
from clients.bybit_helpers import api_call_with_retry
from utils.cache import async_cache
from .realtime_data_stream import realtime_stream, get_realtime_price

logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    """Container for comprehensive market data"""
    symbol: str
    current_price: float
    price_24h_change: float
    price_24h_change_pct: float
    volume_24h: float
    high_24h: float
    low_24h: float
    
    # Kline data for different timeframes
    kline_1h: List[List] = None
    kline_4h: List[List] = None
    kline_1d: List[List] = None
    
    # Order book data
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_ask_spread: Optional[float] = None
    
    # Additional metrics
    turnover_24h: Optional[float] = None
    open_interest: Optional[float] = None
    funding_rate: Optional[float] = None
    open_interest_change_24h: Optional[float] = None  # NEW: 24h OI change percentage
    volume_ratio: Optional[float] = None  # NEW: Current volume vs average
    oi_data_confidence: Optional[str] = None  # NEW: OI data quality indicator
    
    # Metadata
    collected_at: datetime = None
    data_quality: float = 0.0  # 0-100 score

class MarketDataCollector:
    """Real-time market data collection and caching system"""
    
    def __init__(self):
        self.cache_ttl = 60  # 1 minute for real-time market data
        self.kline_cache = {}  # Symbol -> timeframe -> data
        self.ticker_cache = {}  # Symbol -> ticker data
        self.last_update = {}  # Symbol -> timestamp
        
        # Default symbols to track for market overview
        self.primary_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT",
            "XRPUSDT", "DOTUSDT", "AVAXUSDT", "MATICUSDT", "LTCUSDT"
        ]
        
    async def collect_market_data(self, symbol: str) -> MarketData:
        """
        Collect comprehensive market data for a symbol
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            
        Returns:
            MarketData object with all collected information
        """
        try:
            logger.info(f"📊 Collecting market data for {symbol}")
            
            # Collect data in parallel for efficiency
            tasks = [
                self._get_ticker_data(symbol),
                self._get_kline_data(symbol, "60", 100),   # 1h, 100 candles
                self._get_kline_data(symbol, "240", 50),   # 4h, 50 candles  
                self._get_kline_data(symbol, "D", 30),     # 1d, 30 candles
                self._get_orderbook_data(symbol),
                self._get_additional_metrics(symbol)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Unpack results
            ticker_data = results[0] if not isinstance(results[0], Exception) else {}
            kline_1h = results[1] if not isinstance(results[1], Exception) else []
            kline_4h = results[2] if not isinstance(results[2], Exception) else []
            kline_1d = results[3] if not isinstance(results[3], Exception) else []
            orderbook_data = results[4] if not isinstance(results[4], Exception) else {}
            additional_data = results[5] if not isinstance(results[5], Exception) else {}
            
            # Extract ticker information
            current_price = float(ticker_data.get("lastPrice", 0))
            price_24h_change = float(ticker_data.get("price24hPcnt", 0)) * 100  # Convert to percentage
            volume_24h = float(ticker_data.get("volume24h", 0))
            high_24h = float(ticker_data.get("highPrice24h", 0))
            low_24h = float(ticker_data.get("lowPrice24h", 0))
            turnover_24h = float(ticker_data.get("turnover24h", 0))
            
            # Use real-time price if available (more current than REST API)
            realtime_price = get_realtime_price(symbol)
            if realtime_price and realtime_price > 0:
                logger.debug(f"Using real-time price for {symbol}: {realtime_price:.6f} (REST: {current_price:.6f})")
                current_price = realtime_price
            
            # Calculate absolute price change
            if current_price and price_24h_change:
                price_24h_change_abs = current_price * (price_24h_change / 100)
            else:
                price_24h_change_abs = 0
            
            # Extract order book information
            bid_price = float(orderbook_data.get("bid_price", 0)) if orderbook_data.get("bid_price") else None
            ask_price = float(orderbook_data.get("ask_price", 0)) if orderbook_data.get("ask_price") else None
            bid_ask_spread = (ask_price - bid_price) / current_price * 100 if bid_price and ask_price and current_price else None
            
            # Extract additional metrics
            open_interest = additional_data.get("open_interest")
            funding_rate = additional_data.get("funding_rate")
            open_interest_change_24h = additional_data.get("open_interest_change_24h")
            oi_data_confidence = additional_data.get("oi_data_confidence")
            
            # Calculate volume ratio using 30-day average for more accurate baseline
            volume_ratio = None
            if kline_1d and len(kline_1d) >= 15:  # At least 15 days of data
                # Extract 24h volume from daily kline data
                daily_volumes = [float(candle[5]) for candle in kline_1d]  # Volume is index 5
                # Use available data up to 30 days
                sample_size = min(len(daily_volumes), 30)
                avg_daily_volume = sum(daily_volumes[:sample_size]) / sample_size
                if avg_daily_volume > 0:
                    volume_ratio = volume_24h / avg_daily_volume
                    logger.debug(f"Volume ratio for {symbol}: {volume_ratio:.2f}x (current: {volume_24h:,.0f}, 30d avg: {avg_daily_volume:,.0f})")
            elif kline_1h and len(kline_1h) >= 20:
                # Fallback to hourly data if daily data insufficient
                volumes = [float(candle[5]) for candle in kline_1h]
                avg_volume = sum(volumes[-20:]) / 20
                if avg_volume > 0:
                    volume_ratio = volume_24h / avg_volume
            
            # Calculate data quality score
            data_quality = self._calculate_data_quality(
                ticker_data, kline_1h, kline_4h, kline_1d, orderbook_data, additional_data
            )
            
            market_data = MarketData(
                symbol=symbol,
                current_price=current_price,
                price_24h_change=price_24h_change_abs,
                price_24h_change_pct=price_24h_change,
                volume_24h=volume_24h,
                high_24h=high_24h,
                low_24h=low_24h,
                
                # Kline data
                kline_1h=kline_1h,
                kline_4h=kline_4h,
                kline_1d=kline_1d,
                
                # Order book
                bid_price=bid_price,
                ask_price=ask_price,
                bid_ask_spread=bid_ask_spread,
                
                # Additional metrics
                turnover_24h=turnover_24h,
                open_interest=open_interest,
                funding_rate=funding_rate,
                open_interest_change_24h=open_interest_change_24h,
                volume_ratio=volume_ratio,
                oi_data_confidence=oi_data_confidence,
                
                # Metadata
                collected_at=datetime.now(),
                data_quality=data_quality
            )
            
            logger.info(f"✅ Market data collected for {symbol} - Quality: {data_quality:.1f}%")
            return market_data
            
        except Exception as e:
            logger.error(f"❌ Error collecting market data for {symbol}: {e}")
            return MarketData(
                symbol=symbol,
                current_price=0,
                price_24h_change=0,
                price_24h_change_pct=0,
                volume_24h=0,
                high_24h=0,
                low_24h=0,
                collected_at=datetime.now(),
                data_quality=0.0
            )
    
    @async_cache(ttl_seconds=60)  # 1-minute cache for ticker data
    async def _get_ticker_data(self, symbol: str) -> Dict:
        """Get 24hr ticker statistics"""
        try:
            response = await api_call_with_retry(
                lambda: bybit_client.get_tickers(
                    category="linear",
                    symbol=symbol
                ),
                timeout=30
            )
            
            if response and response.get("retCode") == 0:
                tickers = response.get("result", {}).get("list", [])
                if tickers:
                    return tickers[0]
            
            logger.warning(f"⚠️ No ticker data found for {symbol}")
            return {}
            
        except Exception as e:
            logger.error(f"❌ Error getting ticker data for {symbol}: {e}")
            return {}
    
    @async_cache(ttl_seconds=300)  # 5-minute cache for kline data
    async def _get_kline_data(self, symbol: str, interval: str, limit: int = 100) -> List[List]:
        """Get kline/candlestick data"""
        try:
            response = await api_call_with_retry(
                lambda: bybit_client.get_kline(
                    category="linear",
                    symbol=symbol,
                    interval=interval,
                    limit=limit
                ),
                timeout=30
            )
            
            if response and response.get("retCode") == 0:
                klines = response.get("result", {}).get("list", [])
                # Convert to standard format: [timestamp, open, high, low, close, volume]
                formatted_klines = []
                for kline in klines:
                    formatted_klines.append([
                        int(kline[0]),      # timestamp
                        float(kline[1]),    # open
                        float(kline[2]),    # high
                        float(kline[3]),    # low
                        float(kline[4]),    # close
                        float(kline[5])     # volume
                    ])
                
                # Sort by timestamp (oldest first)
                formatted_klines.sort(key=lambda x: x[0])
                return formatted_klines
            
            logger.warning(f"⚠️ No kline data found for {symbol} {interval}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting kline data for {symbol} {interval}: {e}")
            return []
    
    @async_cache(ttl_seconds=30)  # 30-second cache for order book
    async def _get_orderbook_data(self, symbol: str) -> Dict:
        """Get order book data for bid/ask spread analysis"""
        try:
            response = await api_call_with_retry(
                lambda: bybit_client.get_orderbook(
                    category="linear",
                    symbol=symbol,
                    limit=1  # Only need best bid/ask
                ),
                timeout=30
            )
            
            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                bids = result.get("b", [])
                asks = result.get("a", [])
                
                if bids and asks:
                    return {
                        "bid_price": float(bids[0][0]),
                        "ask_price": float(asks[0][0]),
                        "bid_size": float(bids[0][1]),
                        "ask_size": float(asks[0][1])
                    }
            
            logger.warning(f"⚠️ No order book data found for {symbol}")
            return {}
            
        except Exception as e:
            logger.error(f"❌ Error getting order book data for {symbol}: {e}")
            return {}
    
    @async_cache(ttl_seconds=300)  # 5-minute cache for additional metrics
    async def _get_additional_metrics(self, symbol: str) -> Dict:
        """Get additional market metrics like open interest and funding rate"""
        try:
            metrics = {}
            
            # Get open interest with enhanced 24h change calculation
            try:
                oi_response = await api_call_with_retry(
                    lambda: bybit_client.get_open_interest(
                        category="linear",
                        symbol=symbol,
                        intervalTime="5min",
                        limit=300  # Slightly more than 24h to handle edge cases
                    ),
                    timeout=30
                )
                
                if oi_response and oi_response.get("retCode") == 0:
                    oi_data = oi_response.get("result", {}).get("list", [])
                    if oi_data and len(oi_data) > 0:
                        # Current open interest (most recent data point)
                        current_oi = float(oi_data[0].get("openInterest", 0))
                        metrics["open_interest"] = current_oi
                        
                        logger.debug(f"Open Interest data for {symbol}: {len(oi_data)} data points, current OI: {current_oi:,.0f}")
                        
                        # Enhanced 24h change calculation with multiple fallbacks
                        oi_change_24h = None
                        
                        # Method 1: Try exact 24h data (288 intervals of 5min = 24h)
                        if len(oi_data) >= 288:
                            try:
                                oi_24h_ago = float(oi_data[287].get("openInterest", 0))  # Index 287 = 24h ago
                                if oi_24h_ago > 0:
                                    oi_change_24h = ((current_oi - oi_24h_ago) / oi_24h_ago) * 100
                                    logger.debug(f"24h OI change for {symbol}: {oi_change_24h:.2f}% (exact 24h)")
                            except (IndexError, ValueError, ZeroDivisionError) as e:
                                logger.debug(f"Error calculating exact 24h OI change for {symbol}: {e}")
                        
                        # Method 2: Fallback to closest available data (22-26h range)
                        if oi_change_24h is None and len(oi_data) >= 250:  # At least ~21h of data
                            try:
                                # Find the data point closest to 24h ago
                                target_index = min(287, len(oi_data) - 1)
                                oi_reference = float(oi_data[target_index].get("openInterest", 0))
                                if oi_reference > 0:
                                    oi_change_24h = ((current_oi - oi_reference) / oi_reference) * 100
                                    hours_back = (target_index + 1) * 5 / 60  # Convert 5min intervals to hours
                                    logger.debug(f"24h OI change for {symbol}: {oi_change_24h:.2f}% (fallback {hours_back:.1f}h)")
                            except (IndexError, ValueError, ZeroDivisionError) as e:
                                logger.debug(f"Error calculating fallback OI change for {symbol}: {e}")
                        
                        # Method 3: Use last available data point if still no calculation
                        if oi_change_24h is None and len(oi_data) >= 2:
                            try:
                                oi_oldest = float(oi_data[-1].get("openInterest", 0))
                                if oi_oldest > 0:
                                    oi_change_24h = ((current_oi - oi_oldest) / oi_oldest) * 100
                                    hours_back = len(oi_data) * 5 / 60  # Convert to hours
                                    logger.debug(f"24h OI change for {symbol}: {oi_change_24h:.2f}% (best available {hours_back:.1f}h)")
                            except (ValueError, ZeroDivisionError) as e:
                                logger.debug(f"Error calculating best available OI change for {symbol}: {e}")
                        
                        # Store the calculated change
                        if oi_change_24h is not None:
                            metrics["open_interest_change_24h"] = oi_change_24h
                            
                            # Add confidence indicator based on data availability
                            if len(oi_data) >= 288:
                                metrics["oi_data_confidence"] = "high"
                            elif len(oi_data) >= 250:
                                metrics["oi_data_confidence"] = "medium"
                            else:
                                metrics["oi_data_confidence"] = "low"
                        else:
                            logger.warning(f"Could not calculate OI change for {symbol} despite {len(oi_data)} data points")
                    else:
                        logger.warning(f"No open interest data found for {symbol}")
                else:
                    logger.warning(f"Invalid open interest response for {symbol}: {oi_response}")
            except Exception as e:
                logger.warning(f"Error getting open interest for {symbol}: {e}")
                # Set basic metrics even on error
                metrics["open_interest"] = None
                metrics["open_interest_change_24h"] = None
                metrics["oi_data_confidence"] = "error"
            
            # Get funding rate with enhanced error handling
            try:
                funding_response = await api_call_with_retry(
                    lambda: bybit_client.get_funding_rate_history(
                        category="linear",
                        symbol=symbol,
                        limit=1
                    ),
                    timeout=30
                )
                
                if funding_response and funding_response.get("retCode") == 0:
                    funding_data = funding_response.get("result", {}).get("list", [])
                    if funding_data:
                        funding_rate_raw = float(funding_data[0].get("fundingRate", 0))
                        funding_rate_pct = funding_rate_raw * 100  # Convert to percentage
                        funding_timestamp = funding_data[0].get("fundingRateTimestamp")
                        
                        metrics["funding_rate"] = funding_rate_pct
                        metrics["funding_timestamp"] = funding_timestamp
                        
                        logger.debug(f"Funding rate for {symbol}: {funding_rate_pct:.4f}% (timestamp: {funding_timestamp})")
                else:
                    logger.warning(f"Invalid funding rate response for {symbol}: {funding_response}")
            except Exception as e:
                logger.debug(f"Could not get funding rate for {symbol}: {e}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error getting additional metrics for {symbol}: {e}")
            return {}
    
    def _calculate_data_quality(self, ticker_data: Dict, kline_1h: List,
                               kline_4h: List, kline_1d: List,
                               orderbook_data: Dict, additional_data: Dict) -> float:
        """Calculate data quality score (0-100)"""
        quality_factors = []
        
        # Ticker data quality
        if ticker_data and ticker_data.get("lastPrice"):
            quality_factors.append(100)
        else:
            quality_factors.append(0)
        
        # Kline data quality
        kline_score = 0
        if len(kline_1h) >= 50:
            kline_score += 40
        elif len(kline_1h) >= 20:
            kline_score += 25
        
        if len(kline_4h) >= 20:
            kline_score += 30
        elif len(kline_4h) >= 10:
            kline_score += 15
        
        if len(kline_1d) >= 15:
            kline_score += 30
        elif len(kline_1d) >= 7:
            kline_score += 15
        
        quality_factors.append(kline_score)
        
        # Order book data quality
        if orderbook_data and orderbook_data.get("bid_price") and orderbook_data.get("ask_price"):
            quality_factors.append(100)
        else:
            quality_factors.append(50)  # Not critical for analysis
        
        # Additional data quality
        additional_score = 0
        if additional_data.get("open_interest"):
            additional_score += 50
        if additional_data.get("funding_rate"):
            additional_score += 50
        quality_factors.append(additional_score)
        
        # Calculate weighted average
        weights = [0.4, 0.4, 0.1, 0.1]  # Ticker and kline data are most important
        weighted_score = sum(score * weight for score, weight in zip(quality_factors, weights))
        
        return min(weighted_score, 100.0)
    
    async def get_market_overview(self, symbols: Optional[List[str]] = None) -> Dict[str, MarketData]:
        """Get market overview for multiple symbols"""
        if symbols is None:
            symbols = self.primary_symbols
        
        logger.info(f"📊 Collecting market overview for {len(symbols)} symbols")
        
        # Collect data for all symbols in parallel
        tasks = [self.collect_market_data(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        overview = {}
        for symbol, result in zip(symbols, results):
            if not isinstance(result, Exception):
                overview[symbol] = result
            else:
                logger.error(f"❌ Failed to collect data for {symbol}: {result}")
        
        logger.info(f"✅ Market overview collected for {len(overview)}/{len(symbols)} symbols")
        return overview
    
    async def get_primary_symbol_data(self, positions: List[Dict]) -> MarketData:
        """Get market data for the primary trading symbol based on positions"""
        if not positions:
            # Default to BTCUSDT if no positions
            return await self.collect_market_data("BTCUSDT")
        
        # Find symbol with largest position size
        largest_position = max(positions, key=lambda p: float(p.get('size', 0)))
        primary_symbol = largest_position.get('symbol', 'BTCUSDT')
        
        return await self.collect_market_data(primary_symbol)

# Global instance
market_data_collector = MarketDataCollector()