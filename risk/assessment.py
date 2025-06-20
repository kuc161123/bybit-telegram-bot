#!/usr/bin/env python3
"""
AI risk assessment and scoring functionality.
"""
import asyncio
import json
import logging
from decimal import Decimal
from typing import Dict, Any
from telegram.ext import ContextTypes
from clients.ai_client import openai_client
from config.settings import LLM_PROVIDER
from .calculations import calculate_risk_reward_ratio

logger = logging.getLogger(__name__)

def _get_ai_risk_assessment_openai_sync(trade_inputs: Dict, market_context: Dict, bot_context: ContextTypes.DEFAULT_TYPE) -> Dict:
    """OpenAI-powered risk assessment"""
    global openai_client
    logger.info(f"[_get_ai_risk_assessment_openai_sync] Calculating risk for {trade_inputs.get('symbol', 'N/A_SYMBOL')}")
    
    prompt_system = "You are an expert risk analyst for cryptocurrency futures trading. Provide comprehensive risk assessment in JSON format ONLY. Do not use markdown like ```json."
    
    # Calculate basic risk metrics
    entry_price = trade_inputs.get('primary_entry_price', Decimal(0))
    tp1_price = trade_inputs.get('tp1_price', Decimal(0))
    sl_price = trade_inputs.get('sl_price', Decimal(0))
    side = trade_inputs.get('side', 'Buy')
    leverage = trade_inputs.get('leverage', 1)
    margin_amount = trade_inputs.get('margin_amount', Decimal(0))
    
    # Calculate R:R ratio for context
    rr_info = calculate_risk_reward_ratio(entry_price, tp1_price, sl_price, side)
    
    prompt_user = f"""Analyze this futures trade and calculate comprehensive risk score:
Trade Details: Symbol: {trade_inputs.get('symbol')}, Side: {side}, Entry: {entry_price}, TP1: {tp1_price}, SL: {sl_price}, Leverage: {leverage}x, Margin: {margin_amount} USDT
Market Context: Current Price: {market_context.get('current_price', 'N/A')}, 24h Change: {market_context.get('price_24h_pcnt_str', 'N/A')}, Volatility: {market_context.get('volatility_indicator', 'moderate')}
Risk/Reward Ratio: {rr_info.get('ratio', 'N/A')} ({rr_info.get('analysis', 'N/A')})

Required JSON Output:
{{
    "risk_score": number (1-10 scale, where 10 = highest risk),
    "risk_factors": ["factor1", "factor2", ...],
    "suggestions": ["suggestion1", "suggestion2", ...],
    "confidence": number (0-1 scale),
    "position_size_recommendation": "reduce|maintain|increase",
    "risk_level": "low|medium|high|very_high",
    "error": null|"Error message"
}}

Consider: leverage exposure, R:R ratio, market volatility, position sizing, technical levels, and current market conditions. Output ONLY JSON."""
    
    try:
        chat_completion = openai_client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        response_content = chat_completion.choices[0].message.content
        logger.info(f"[_get_ai_risk_assessment_openai_sync] Raw response: {response_content}")
        
        risk_data = json.loads(response_content)
        
        # Validate and normalize the response
        validated_risk = {
            "risk_score": float(risk_data.get("risk_score", 5.0)),
            "risk_factors": risk_data.get("risk_factors", []),
            "suggestions": risk_data.get("suggestions", []),
            "confidence": float(risk_data.get("confidence", 0.7)),
            "position_size_recommendation": risk_data.get("position_size_recommendation", "maintain"),
            "risk_level": risk_data.get("risk_level", "medium"),
            "error": risk_data.get("error")
        }
        
        # Ensure risk_score is within bounds
        validated_risk["risk_score"] = max(1.0, min(10.0, validated_risk["risk_score"]))
        validated_risk["confidence"] = max(0.0, min(1.0, validated_risk["confidence"]))
        
        logger.info(f"[_get_ai_risk_assessment_openai_sync] Validated risk assessment: {validated_risk}")
        return validated_risk
        
    except json.JSONDecodeError as e_json:
        logger.error(f"[_get_ai_risk_assessment_openai_sync] JSONDecodeError: {e_json}")
        return {"error": "AI response not valid JSON."}
    except Exception as e_openai:
        logger.error(f"[_get_ai_risk_assessment_openai_sync] OpenAI error: {e_openai}", exc_info=True)
        return {"error": f"OpenAI API error: {str(e_openai)[:100]}"}

async def calculate_ai_risk_score(trade_inputs: Dict, market_context: Dict, bot_context: ContextTypes.DEFAULT_TYPE) -> Dict:
    """AI calculates comprehensive risk score"""
    logger.info(f"[calculate_ai_risk_score] Calculating risk assessment. Provider: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == "openai" and openai_client:
        logger.info("[calculate_ai_risk_score] Using OpenAI for risk assessment")
        risk_assessment = await asyncio.to_thread(_get_ai_risk_assessment_openai_sync, trade_inputs, market_context, bot_context)
        logger.info(f"[calculate_ai_risk_score] OpenAI risk assessment: {risk_assessment}")
        return risk_assessment
    
    # Enhanced stub implementation with smart calculations
    logger.info(f"[calculate_ai_risk_score] Using STUB risk assessment for {trade_inputs.get('symbol', 'N/A')}")
    await asyncio.sleep(0.2)  # Simulate processing
    
    try:
        # Calculate risk factors based on trade parameters
        risk_factors = []
        suggestions = []
        risk_score = 5.0  # Base risk score
        
        # Analyze leverage
        leverage = trade_inputs.get('leverage', 1)
        if leverage > 20:
            risk_factors.append("Very high leverage exposure")
            suggestions.append("Consider reducing leverage below 20x")
            risk_score += 2.0
        elif leverage > 10:
            risk_factors.append("High leverage exposure")
            suggestions.append("Monitor position closely due to high leverage")
            risk_score += 1.0
        
        # Analyze R:R ratio
        entry_price = trade_inputs.get('primary_entry_price', Decimal(0))
        tp1_price = trade_inputs.get('tp1_price', Decimal(0))
        sl_price = trade_inputs.get('sl_price', Decimal(0))
        side = trade_inputs.get('side', 'Buy')
        
        if all([entry_price, tp1_price, sl_price]):
            rr_info = calculate_risk_reward_ratio(entry_price, tp1_price, sl_price, side)
            if not rr_info.get('error'):
                rr_ratio = rr_info.get('decimal_ratio', 1.0)
                if rr_ratio < 1.5:
                    risk_factors.append("Poor risk/reward ratio")
                    suggestions.append("Consider better entry or TP/SL levels")
                    risk_score += 1.5
                elif rr_ratio > 3:
                    suggestions.append("Excellent R:R ratio - good setup")
                    risk_score -= 0.5
        
        # Analyze market volatility
        volatility = market_context.get('volatility_indicator', 'moderate')
        if volatility == 'high':
            risk_factors.append("High market volatility")
            suggestions.append("Consider tighter stop loss")
            risk_score += 1.0
        elif volatility == 'low':
            suggestions.append("Low volatility - stable conditions")
            risk_score -= 0.5
        
        # Analyze position size
        margin_amount = trade_inputs.get('margin_amount', Decimal(0))
        if margin_amount > Decimal(1000):
            risk_factors.append("Large position size")
            suggestions.append("Consider position sizing relative to portfolio")
            risk_score += 0.5
        
        # Analyze price movement
        try:
            price_change_str = market_context.get('price_24h_pcnt_str', '0%')
            price_change = float(price_change_str.replace('%', ''))
            if abs(price_change) > 5:
                risk_factors.append(f"High 24h price movement ({price_change:+.1f}%)")
                suggestions.append("Exercise caution with volatile market")
                risk_score += 0.5
        except:
            pass
        
        # Ensure risk score is within bounds
        risk_score = max(1.0, min(10.0, risk_score))
        
        # Determine risk level
        if risk_score <= 3:
            risk_level = "low"
        elif risk_score <= 6:
            risk_level = "medium"
        elif risk_score <= 8:
            risk_level = "high"
        else:
            risk_level = "very_high"
        
        # Position size recommendation
        if risk_score > 7:
            position_recommendation = "reduce"
        elif risk_score < 4:
            position_recommendation = "increase"
        else:
            position_recommendation = "maintain"
        
        # Default suggestions if none added
        if not suggestions:
            suggestions = ["Trade setup looks reasonable", "Monitor position after entry"]
        
        if not risk_factors:
            risk_factors = ["Standard market risk"]
        
        risk_assessment = {
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "suggestions": suggestions,
            "confidence": 0.85,
            "position_size_recommendation": position_recommendation,
            "risk_level": risk_level,
            "error": None
        }
        
        logger.info(f"[calculate_ai_risk_score] Stub risk assessment completed: {risk_assessment}")
        return risk_assessment
        
    except Exception as e:
        logger.error(f"[calculate_ai_risk_score] Error in stub calculation: {e}", exc_info=True)
        return {
            "risk_score": 5.0,
            "risk_factors": ["Risk calculation error"],
            "suggestions": ["Manual risk assessment recommended"],
            "confidence": 0.5,
            "position_size_recommendation": "maintain",
            "risk_level": "medium",
            "error": f"Calculation error: {str(e)}"
        }

# Add the function that dashboard/generator.py is looking for
async def get_ai_risk_assessment(symbol: str, entry_price: Decimal, 
                                tp1_price: Decimal, sl_price: Decimal, 
                                side: str, leverage: int, 
                                margin_amount: Decimal) -> Dict:
    """
    Get AI risk assessment for a trade setup.
    This is a wrapper for calculate_ai_risk_score to match the expected function name.
    """
    # Build trade inputs dictionary
    trade_inputs = {
        'symbol': symbol,
        'primary_entry_price': entry_price,
        'tp1_price': tp1_price,
        'sl_price': sl_price,
        'side': side,
        'leverage': leverage,
        'margin_amount': margin_amount
    }
    
    # Build market context (simplified - would be better with real market data)
    market_context = {
        'current_price': entry_price,  # Approximation
        'price_24h_pcnt_str': '0%',    # Would need real data
        'volatility_indicator': 'moderate'
    }
    
    # Call the existing function
    return await calculate_ai_risk_score(trade_inputs, market_context, None)