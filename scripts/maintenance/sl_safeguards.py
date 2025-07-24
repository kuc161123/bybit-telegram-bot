
# Enhanced TP/SL Manager Safeguards - Add to enhanced_tp_sl_manager.py

async def verify_sl_order_creation(self, symbol: str, side: str, expected_quantity: Decimal) -> bool:
    """Verify that SL order was actually created"""
    try:
        await asyncio.sleep(2)  # Wait for order to appear
        
        orders = await get_open_orders(symbol)
        for order in orders:
            if (order.get('stopOrderType') == 'StopLoss' and 
                float(order.get('qty', 0)) >= float(expected_quantity) * 0.95):
                return True
        return False
    except:
        return False

async def create_verified_sl_order(self, symbol: str, side: str, position_size: Decimal, 
                                 sl_price: Decimal, position_idx: int = 0) -> Dict:
    """Create SL order with verification and retry"""
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Calculate SL side
            sl_side = "Sell" if side == "Buy" else "Buy"
            
            # Create SL order
            sl_result = await place_order_with_retry(
                symbol=symbol,
                side=sl_side,
                order_type="Market",
                qty=str(position_size),
                trigger_price=str(sl_price),
                reduce_only=True,
                order_link_id=f"BOT_VERIFIED_SL_{symbol}_{int(time.time())}_{attempt}",
                position_idx=position_idx,
                stop_order_type="StopLoss"
            )
            
            if sl_result and sl_result.get('orderId'):
                # Verify the order exists
                if await self.verify_sl_order_creation(symbol, side, position_size):
                    logger.info(f"✅ Verified SL order created: {sl_result['orderId']}")
                    return sl_result
                else:
                    logger.warning(f"⚠️  SL order created but not verified, retrying...")
            
        except Exception as e:
            logger.error(f"❌ SL creation attempt {attempt + 1} failed: {e}")
            
        if attempt < max_attempts - 1:
            await asyncio.sleep(1)  # Wait before retry
    
    logger.error(f"❌ Failed to create verified SL after {max_attempts} attempts")
    return None

async def monitor_sl_trigger_prices(self, symbol: str, side: str, sl_price: Decimal, 
                                  position_size: Decimal):
    """Monitor if SL trigger price is hit and manually close if SL fails"""
    
    try:
        current_price = await get_current_price(symbol)
        current_price = Decimal(str(current_price))
        
        # Check if SL should have triggered
        should_trigger = False
        if side == "Buy" and current_price <= sl_price:
            should_trigger = True
        elif side == "Sell" and current_price >= sl_price:
            should_trigger = True
        
        if should_trigger:
            # Check if position still exists
            positions = await get_position_info(symbol)
            position_exists = False
            
            for pos in positions:
                if (pos.get('side') == side and 
                    float(pos.get('size', 0)) > 0):
                    position_exists = True
                    break
            
            if position_exists:
                logger.error(f"🚨 SL FAILURE DETECTED: {symbol} {side}")
                logger.error(f"   Current price: {current_price}")
                logger.error(f"   SL trigger: {sl_price}")
                
                # Send critical alert
                await self.send_critical_sl_failure_alert(symbol, side, current_price, sl_price)
                
                # Execute emergency manual close
                await self.emergency_manual_close(symbol, side, position_size)
                
    except Exception as e:
        logger.error(f"Error monitoring SL trigger for {symbol}: {e}")

async def emergency_manual_close(self, symbol: str, side: str, position_size: Decimal):
    """Emergency manual position close when SL fails"""
    
    try:
        close_side = "Sell" if side == "Buy" else "Buy"
        
        logger.warning(f"🚨 EXECUTING EMERGENCY MANUAL CLOSE: {symbol} {side}")
        
        close_result = await place_order_with_retry(
            symbol=symbol,
            side=close_side,
            order_type="Market",
            qty=str(position_size),
            reduce_only=True,
            order_link_id=f"BOT_EMERGENCY_CLOSE_{symbol}_{int(time.time())}",
            position_idx=0
        )
        
        if close_result and close_result.get('orderId'):
            logger.info(f"✅ Emergency manual close executed: {close_result['orderId']}")
            return True
        else:
            logger.error(f"❌ Emergency manual close failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in emergency manual close: {e}")
        return False

async def send_critical_sl_failure_alert(self, symbol: str, side: str, 
                                       current_price: Decimal, sl_price: Decimal):
    """Send critical alert for SL failure"""
    
    message = f"""🚨 CRITICAL STOP LOSS FAILURE 🚨

Symbol: {symbol}
Side: {side}
Current Price: {current_price}
SL Trigger Price: {sl_price}

⚠️ Stop loss failed to execute!
⚠️ Emergency manual close initiated
⚠️ Immediate attention required

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    try:
        await send_trade_alert(message, priority="CRITICAL")
        logger.critical(f"SL FAILURE ALERT SENT: {symbol} {side}")
    except:
        logger.error("Failed to send SL failure alert")
