#!/usr/bin/env python3
"""
Accuracy Metrics Tracker for Enhanced Market Analysis
Tracks and evaluates the accuracy of predictions and analysis
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class PredictionRecord:
    """Record of a prediction for tracking"""
    timestamp: datetime
    symbol: str
    prediction_type: str  # "direction", "regime", "pattern"
    predicted_value: str
    confidence: float
    actual_value: Optional[str] = None
    time_horizon: int = 24  # hours
    is_correct: Optional[bool] = None
    error_margin: Optional[float] = None


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for a component"""
    component: str
    total_predictions: int
    correct_predictions: int
    accuracy: float
    avg_confidence: float
    confidence_correlation: float  # Correlation between confidence and accuracy
    precision_by_type: Dict[str, float]
    recall_by_type: Dict[str, float]
    f1_score: float
    mean_absolute_error: Optional[float] = None


class AccuracyMetricsTracker:
    """Track and evaluate accuracy of market analysis predictions"""
    
    def __init__(self):
        self.predictions: List[PredictionRecord] = []
        self.metrics_history: Dict[str, List[AccuracyMetrics]] = {}
        self.load_historical_predictions()
    
    def load_historical_predictions(self):
        """Load historical predictions from storage"""
        try:
            if os.path.exists("prediction_history.json"):
                with open("prediction_history.json", "r") as f:
                    data = json.load(f)
                    # Convert back to PredictionRecord objects
                    self.predictions = [
                        PredictionRecord(**{
                            **record,
                            "timestamp": datetime.fromisoformat(record["timestamp"])
                        })
                        for record in data
                    ]
                logger.info(f"Loaded {len(self.predictions)} historical predictions")
        except Exception as e:
            logger.error(f"Error loading predictions: {e}")
    
    def save_predictions(self):
        """Save predictions to storage"""
        try:
            data = [
                {
                    **asdict(pred),
                    "timestamp": pred.timestamp.isoformat()
                }
                for pred in self.predictions
            ]
            with open("prediction_history.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving predictions: {e}")
    
    async def track_market_regime_accuracy(self):
        """Track accuracy of market regime predictions"""
        from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
        
        logger.info("📊 Tracking Market Regime Accuracy...")
        
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        predictions_made = []
        
        for symbol in symbols:
            # Get current prediction
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol=symbol,
                enable_ai_analysis=False
            )
            
            # Record prediction
            prediction = PredictionRecord(
                timestamp=datetime.now(),
                symbol=symbol,
                prediction_type="market_regime",
                predicted_value=status.market_regime,
                confidence=status.confidence,
                time_horizon=24
            )
            
            predictions_made.append(prediction)
            self.predictions.append(prediction)
            
            logger.info(f"  {symbol}: Predicted {status.market_regime} ({status.confidence:.1f}% confidence)")
        
        # Check past predictions that are due
        await self._evaluate_due_predictions()
        
        return predictions_made
    
    async def track_pattern_accuracy(self):
        """Track accuracy of pattern predictions"""
        from market_analysis.pattern_recognition import pattern_recognition_engine
        from clients.bybit_client import bybit_client
        
        logger.info("📈 Tracking Pattern Prediction Accuracy...")
        
        symbol = "BTCUSDT"
        
        # Get kline data
        kline_response = bybit_client.get_kline(
            category="linear",
            symbol=symbol,
            interval="5",
            limit=100
        )
        
        if kline_response.get("retCode") == 0:
            klines = kline_response.get("result", {}).get("list", [])
            kline_data = {"5m": klines, "15m": klines[::3], "1h": klines[::12]}
            
            # Analyze patterns
            analysis = await pattern_recognition_engine.analyze_patterns(
                symbol=symbol,
                kline_data=kline_data,
                current_price=float(klines[0][4]) if klines else 100000
            )
            
            # Track patterns with targets
            for pattern in analysis.chart_patterns:
                if pattern.target_price and pattern.confidence > 60:
                    prediction = PredictionRecord(
                        timestamp=datetime.now(),
                        symbol=symbol,
                        prediction_type="pattern_target",
                        predicted_value=f"{pattern.pattern_name}:{pattern.target_price}",
                        confidence=pattern.confidence,
                        time_horizon=72  # 3 days for pattern targets
                    )
                    
                    self.predictions.append(prediction)
                    logger.info(f"  Pattern: {pattern.pattern_name} target ${pattern.target_price:,.0f} ({pattern.confidence:.1f}% confidence)")
    
    async def track_ai_recommendation_accuracy(self):
        """Track accuracy of AI recommendations"""
        from execution.ai_market_analysis import AIMarketAnalyzer
        from clients.bybit_client import bybit_client
        from clients.ai_client import get_ai_client
        
        logger.info("🤖 Tracking AI Recommendation Accuracy...")
        
        ai_client = get_ai_client()
        if ai_client.llm_provider == "stub":
            logger.info("  Skipping AI tracking (stub client)")
            return
        
        analyzer = AIMarketAnalyzer(bybit_client, ai_client)
        
        symbol = "BTCUSDT"
        insight = await analyzer.analyze_market(symbol)
        
        if insight and insight.recommendation:
            prediction = PredictionRecord(
                timestamp=datetime.now(),
                symbol=symbol,
                prediction_type="ai_recommendation",
                predicted_value=insight.recommendation,
                confidence=insight.confidence,
                time_horizon=48  # 2 days
            )
            
            self.predictions.append(prediction)
            logger.info(f"  AI: {insight.recommendation} ({insight.confidence:.1f}% confidence)")
    
    async def _evaluate_due_predictions(self):
        """Evaluate predictions that have reached their time horizon"""
        due_predictions = [
            p for p in self.predictions
            if p.actual_value is None and 
            (datetime.now() - p.timestamp).total_seconds() / 3600 >= p.time_horizon
        ]
        
        logger.info(f"\n⏰ Evaluating {len(due_predictions)} due predictions...")
        
        for pred in due_predictions:
            actual = await self._get_actual_outcome(pred)
            if actual:
                pred.actual_value = actual
                pred.is_correct = self._evaluate_prediction(pred)
                logger.info(f"  {pred.symbol} {pred.prediction_type}: "
                          f"Predicted={pred.predicted_value}, Actual={actual}, "
                          f"Correct={pred.is_correct}")
        
        self.save_predictions()
    
    async def _get_actual_outcome(self, prediction: PredictionRecord) -> Optional[str]:
        """Get actual outcome for a prediction"""
        # In production, this would fetch real market data
        # For now, simulate with current market status
        
        if prediction.prediction_type == "market_regime":
            from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol=prediction.symbol,
                enable_ai_analysis=False
            )
            return status.market_regime
        
        elif prediction.prediction_type == "pattern_target":
            # Would check if target was reached
            from clients.bybit_client import bybit_client
            ticker = bybit_client.get_tickers(
                category="linear",
                symbol=prediction.symbol
            )
            if ticker.get("retCode") == 0:
                current_price = float(ticker.get("result", {}).get("list", [{}])[0].get("lastPrice", 0))
                pattern_name, target = prediction.predicted_value.split(":")
                target_price = float(target)
                
                # Check if price reached target
                if "Top" in pattern_name or "Bearish" in pattern_name:
                    return "reached" if current_price <= target_price else "not_reached"
                else:
                    return "reached" if current_price >= target_price else "not_reached"
        
        return None
    
    def _evaluate_prediction(self, prediction: PredictionRecord) -> bool:
        """Evaluate if a prediction was correct"""
        if prediction.prediction_type == "market_regime":
            # Exact match for regime
            return prediction.predicted_value == prediction.actual_value
        
        elif prediction.prediction_type == "pattern_target":
            # Target reached
            return "reached" in prediction.actual_value
        
        elif prediction.prediction_type == "ai_recommendation":
            # Would evaluate based on price movement
            # Simplified for now
            return True
        
        return False
    
    def calculate_accuracy_metrics(self, component: str = None) -> List[AccuracyMetrics]:
        """Calculate accuracy metrics for components"""
        metrics = []
        
        # Group predictions by type
        prediction_types = {}
        for pred in self.predictions:
            if pred.actual_value is not None:
                pred_type = pred.prediction_type
                if component and pred_type != component:
                    continue
                    
                if pred_type not in prediction_types:
                    prediction_types[pred_type] = []
                prediction_types[pred_type].append(pred)
        
        # Calculate metrics for each type
        for pred_type, preds in prediction_types.items():
            if not preds:
                continue
                
            total = len(preds)
            correct = sum(1 for p in preds if p.is_correct)
            accuracy = correct / total if total > 0 else 0
            
            avg_confidence = statistics.mean(p.confidence for p in preds)
            
            # Calculate confidence correlation
            if len(preds) > 1:
                confidences = [p.confidence for p in preds]
                correctness = [1 if p.is_correct else 0 for p in preds]
                
                # Simple correlation calculation
                conf_mean = statistics.mean(confidences)
                corr_mean = statistics.mean(correctness)
                
                numerator = sum((c - conf_mean) * (cr - corr_mean) 
                              for c, cr in zip(confidences, correctness))
                denominator = (
                    sum((c - conf_mean) ** 2 for c in confidences) *
                    sum((cr - corr_mean) ** 2 for cr in correctness)
                ) ** 0.5
                
                correlation = numerator / denominator if denominator > 0 else 0
            else:
                correlation = 0
            
            # Calculate precision/recall by predicted value
            precision_by_type = {}
            recall_by_type = {}
            
            predicted_values = set(p.predicted_value for p in preds)
            for value in predicted_values:
                true_positives = sum(1 for p in preds 
                                   if p.predicted_value == value and p.is_correct)
                false_positives = sum(1 for p in preds 
                                    if p.predicted_value == value and not p.is_correct)
                false_negatives = sum(1 for p in preds 
                                    if p.actual_value == value and p.predicted_value != value)
                
                precision = true_positives / (true_positives + false_positives) \
                           if (true_positives + false_positives) > 0 else 0
                recall = true_positives / (true_positives + false_negatives) \
                        if (true_positives + false_negatives) > 0 else 0
                
                precision_by_type[value] = precision
                recall_by_type[value] = recall
            
            # Calculate F1 score
            avg_precision = statistics.mean(precision_by_type.values()) if precision_by_type else 0
            avg_recall = statistics.mean(recall_by_type.values()) if recall_by_type else 0
            f1_score = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall) \
                      if (avg_precision + avg_recall) > 0 else 0
            
            metrics.append(AccuracyMetrics(
                component=pred_type,
                total_predictions=total,
                correct_predictions=correct,
                accuracy=accuracy,
                avg_confidence=avg_confidence,
                confidence_correlation=correlation,
                precision_by_type=precision_by_type,
                recall_by_type=recall_by_type,
                f1_score=f1_score
            ))
        
        return metrics
    
    def generate_accuracy_report(self) -> Dict:
        """Generate comprehensive accuracy report"""
        logger.info("\n" + "="*60)
        logger.info("📊 ACCURACY METRICS REPORT")
        logger.info("="*60)
        
        metrics = self.calculate_accuracy_metrics()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_predictions": len(self.predictions),
            "evaluated_predictions": sum(1 for p in self.predictions if p.actual_value is not None),
            "pending_predictions": sum(1 for p in self.predictions if p.actual_value is None),
            "component_metrics": []
        }
        
        for metric in metrics:
            logger.info(f"\n{metric.component.upper()}:")
            logger.info(f"  Accuracy: {metric.accuracy:.1%} ({metric.correct_predictions}/{metric.total_predictions})")
            logger.info(f"  Avg Confidence: {metric.avg_confidence:.1f}%")
            logger.info(f"  Confidence Correlation: {metric.confidence_correlation:.3f}")
            logger.info(f"  F1 Score: {metric.f1_score:.3f}")
            
            report["component_metrics"].append(asdict(metric))
        
        # Overall accuracy
        if metrics:
            overall_accuracy = sum(m.accuracy * m.total_predictions for m in metrics) / \
                             sum(m.total_predictions for m in metrics)
            overall_f1 = statistics.mean(m.f1_score for m in metrics)
            
            logger.info(f"\nOVERALL:")
            logger.info(f"  Accuracy: {overall_accuracy:.1%}")
            logger.info(f"  F1 Score: {overall_f1:.3f}")
            
            report["overall_accuracy"] = overall_accuracy
            report["overall_f1_score"] = overall_f1
        
        # Save report
        filename = f"accuracy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\n📄 Report saved to: {filename}")
        logger.info("="*60 + "\n")
        
        return report
    
    async def run_accuracy_tracking(self):
        """Run complete accuracy tracking cycle"""
        logger.info("🎯 Starting Accuracy Tracking Cycle...")
        
        # Track various predictions
        await self.track_market_regime_accuracy()
        await self.track_pattern_accuracy()
        await self.track_ai_recommendation_accuracy()
        
        # Evaluate due predictions
        await self._evaluate_due_predictions()
        
        # Generate report
        report = self.generate_accuracy_report()
        
        return report


async def main():
    """Run accuracy tracking"""
    tracker = AccuracyMetricsTracker()
    await tracker.run_accuracy_tracking()


if __name__ == "__main__":
    # Initialize environment
    import dotenv
    dotenv.load_dotenv()
    
    # Run tracking
    asyncio.run(main())