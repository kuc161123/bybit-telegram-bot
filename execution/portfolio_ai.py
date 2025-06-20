#!/usr/bin/env python3
"""
AI-powered portfolio health analysis and optimization.
"""
import logging
import asyncio
import json
from decimal import Decimal
from typing import Dict, Any

from clients.bybit_helpers import get_all_positions
from utils.cache import get_usdt_wallet_balance_cached, enhanced_cache
from config.constants import *

logger = logging.getLogger(__name__)

class AIPortfolioOptimizer:
    def __init__(self, openai_client=None):
        self.client = openai_client
        
    async def analyze_portfolio_health(self) -> Dict[str, Any]:
        """Analyze overall portfolio health with AI insights"""
        try:
            # Check cache first
            cache_key = "portfolio_health"
            cached = enhanced_cache.get(cache_key)
            if cached:
                return cached
            
            # Get portfolio data
            portfolio_data = await self._get_portfolio_data()
            
            if not self.client:
                # Fallback to technical analysis
                result = await self._get_technical_health(portfolio_data)
            else:
                # Use AI-powered analysis
                result = await self._get_ai_health(portfolio_data)
            
            # Cache for 3 minutes
            enhanced_cache.set(cache_key, result, ttl=180)
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio health: {e}")
            return {
                "score": 50,
                "status": "UNKNOWN",
                "risk_level": "MEDIUM",
                "recommendations": ["Unable to analyze portfolio"],
                "metrics": {},
                "error": str(e)
            }
    
    async def _get_ai_health(self, portfolio_data: Dict) -> Dict[str, Any]:
        """AI-powered portfolio health analysis"""
        try:
            prompt = f"""
            Analyze portfolio health:
            
            Portfolio Data: {portfolio_data}
            
            Evaluate:
            1. Overall health score (0-100)
            2. Portfolio status: EXCELLENT, GOOD, FAIR, POOR, or CRITICAL
            3. Risk level: LOW, MEDIUM, HIGH, or EXTREME
            4. Top 3 recommendations for improvement
            5. Key metrics assessment
            
            Consider:
            - Position concentration
            - Risk exposure
            - P&L performance
            - Balance utilization
            - Diversification
            
            Respond ONLY with valid JSON:
            {{
                "score": 75,
                "status": "GOOD",
                "risk_level": "MEDIUM",
                "recommendations": ["Recommendation 1", "Recommendation 2", "Recommendation 3"],
                "metrics": {{
                    "diversification": "Good",
                    "risk_exposure": "Moderate",
                    "performance": "Positive"
                }}
            }}
            """
            
            # Use proper OpenAI API call with asyncio executor
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=300
                    )
                ),
                timeout=15.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate result
            required_keys = ["score", "status", "risk_level", "recommendations", "metrics"]
            if not all(key in result for key in required_keys):
                raise Exception("Invalid AI response format")
                
            return result
            
        except Exception as e:
            logger.error(f"AI portfolio analysis failed: {e}")
            # Fallback to technical analysis
            return await self._get_technical_health(portfolio_data)
    
    async def _get_technical_health(self, portfolio_data: Dict) -> Dict[str, Any]:
        """Fallback technical portfolio health analysis"""
        try:
            balance = portfolio_data.get("balance", 0)
            positions = portfolio_data.get("positions", [])
            total_pnl = portfolio_data.get("total_unrealized_pnl", 0)
            
            # Calculate health score
            score = 50  # Base score
            
            # Adjust based on P&L
            if total_pnl > 0:
                score += min(25, total_pnl / 10)  # Bonus for profit
            else:
                score += max(-30, total_pnl / 10)  # Penalty for loss
            
            # Adjust based on position count
            pos_count = len(positions)
            if pos_count == 0:
                score += 10  # Bonus for no positions (low risk)
            elif pos_count <= 3:
                score += 5   # Slight bonus for reasonable diversification
            elif pos_count > 5:
                score -= 10  # Penalty for over-diversification
            
            # Adjust based on balance
            if balance > 1000:
                score += 10
            elif balance < 100:
                score -= 15
            
            score = max(0, min(100, int(score)))
            
            # Determine status
            if score >= 80:
                status = "EXCELLENT"
                risk_level = "LOW"
            elif score >= 65:
                status = "GOOD"
                risk_level = "MEDIUM"
            elif score >= 45:
                status = "FAIR"
                risk_level = "MEDIUM"
            elif score >= 25:
                status = "POOR"
                risk_level = "HIGH"
            else:
                status = "CRITICAL"
                risk_level = "EXTREME"
            
            # Generate recommendations
            recommendations = []
            if total_pnl < -50:
                recommendations.append("Consider reducing position sizes")
            if pos_count > 5:
                recommendations.append("Reduce number of open positions")
            if balance < 200:
                recommendations.append("Increase account balance for better risk management")
            
            if not recommendations:
                recommendations.append("Portfolio looks healthy")
            
            return {
                "score": score,
                "status": status,
                "risk_level": risk_level,
                "recommendations": recommendations[:3],
                "metrics": {
                    "positions": f"{pos_count} active",
                    "pnl": f"${total_pnl:.2f}",
                    "balance": f"${balance:.2f}"
                }
            }
            
        except Exception as e:
            logger.error(f"Technical portfolio analysis failed: {e}")
            return {
                "score": 50,
                "status": "UNKNOWN",
                "risk_level": "MEDIUM",
                "recommendations": ["Unable to analyze"],
                "metrics": {}
            }
    
    async def _get_portfolio_data(self) -> Dict[str, Any]:
        """Gather portfolio data for analysis"""
        try:
            # Get balance
            balance = await get_usdt_wallet_balance_cached()
            balance_float = float(balance) if balance else 0
            
            # Get positions
            positions = await get_all_positions()
            active_positions = [p for p in positions if Decimal(str(p.get("size", "0"))) > 0]
            
            # Calculate total unrealized P&L
            total_unrealized_pnl = sum(
                float(p.get("unrealisedPnl", "0")) for p in active_positions
            )
            
            return {
                "balance": balance_float,
                "positions": active_positions,
                "position_count": len(active_positions),
                "total_unrealized_pnl": total_unrealized_pnl,
                "symbols": [p.get("symbol", "") for p in active_positions]
            }
            
        except Exception as e:
            logger.error(f"Error gathering portfolio data: {e}")
            return {
                "balance": 0,
                "positions": [],
                "position_count": 0,
                "total_unrealized_pnl": 0,
                "symbols": []
            }

# Global instance
portfolio_optimizer = AIPortfolioOptimizer()