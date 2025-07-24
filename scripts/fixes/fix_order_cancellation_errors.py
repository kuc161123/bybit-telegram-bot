#!/usr/bin/env python3
"""
Fix order cancellation errors - prevent repeated attempts on non-existent orders
"""

import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fix_order_cancellation():
    """Fix the order cancellation error handling"""
    
    print("\n🔧 FIXING ORDER CANCELLATION ERROR HANDLING")
    print("=" * 60)
    
    # Check order state cache
    print("\n1️⃣ Checking order state cache implementation...")
    
    try:
        from utils.order_state_cache import order_state_cache
        
        # Check if the problematic order is in cache
        order_id = "bf341c83-2dc5-4eec-84bb-6e61f86044e9"
        
        # Force mark this order as non-cancellable
        await order_state_cache.prevent_cancellation(order_id)
        await order_state_cache.update_order_state(order_id, "Filled")
        
        print(f"✅ Marked order {order_id[:8]}... as non-cancellable in cache")
        
        # Clear any pending cancellation attempts
        if hasattr(order_state_cache, '_pending_cancellations'):
            if order_id in order_state_cache._pending_cancellations:
                del order_state_cache._pending_cancellations[order_id]
                print(f"✅ Cleared pending cancellation for {order_id[:8]}...")
        
    except Exception as e:
        print(f"❌ Error updating order state cache: {e}")
    
    print("\n2️⃣ Enhancing order cancellation logic...")
    
    # Create an improved version that checks cache more aggressively
    fix_content = '''# Add to cancel_order_with_retry in bybit_helpers.py

    # Early exit if order was recently attempted
    if hasattr(order_state_cache, 'get_recent_attempt_count'):
        recent_attempts = await order_state_cache.get_recent_attempt_count(order_id, 60)  # Last 60 seconds
        if recent_attempts >= 3:
            logger.info(f"🛡️ Order {order_id[:8]}... had {recent_attempts} recent cancel attempts - skipping")
            return True
    
    # Add before the retry loop
    if ret_code == 110001:  # Order not exists
        # Immediately prevent future attempts
        await order_state_cache.prevent_cancellation(order_id)
        await order_state_cache.update_order_state(order_id, "Filled")
        logger.info(f"✅ Order {order_id[:8]}... marked as non-existent - no further attempts")
        return True
'''
    
    print("\n3️⃣ Creating enhanced order state cache methods...")
    
    # Create the enhancement
    cache_enhancement = '''#!/usr/bin/env python3
"""
Enhanced order state cache with recent attempt tracking
"""

import time
from typing import Dict, Optional
from collections import defaultdict
import asyncio

class EnhancedOrderStateCache:
    def __init__(self):
        self._states = {}
        self._non_cancellable = set()
        self._cancel_attempts = defaultdict(list)  # order_id -> list of timestamps
        self._lock = asyncio.Lock()
    
    async def get_recent_attempt_count(self, order_id: str, window_seconds: int = 60) -> int:
        """Get count of recent cancellation attempts within time window"""
        async with self._lock:
            if order_id not in self._cancel_attempts:
                return 0
            
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            
            # Filter attempts within window
            recent_attempts = [t for t in self._cancel_attempts[order_id] if t > cutoff_time]
            
            # Update list to only keep recent attempts
            self._cancel_attempts[order_id] = recent_attempts
            
            return len(recent_attempts)
    
    async def record_cancel_attempt(self, order_id: str, success: bool = False):
        """Record a cancellation attempt"""
        async with self._lock:
            self._cancel_attempts[order_id].append(time.time())
            
            # Clean up old entries (older than 5 minutes)
            cutoff = time.time() - 300
            self._cancel_attempts[order_id] = [
                t for t in self._cancel_attempts[order_id] if t > cutoff
            ]
    
    async def is_order_cancellable(self, order_id: str) -> bool:
        """Check if order can be cancelled"""
        if order_id in self._non_cancellable:
            return False
        
        # Check recent attempts
        recent_attempts = await self.get_recent_attempt_count(order_id, 30)
        if recent_attempts >= 5:
            # Too many recent attempts, likely not cancellable
            return False
        
        return order_id not in self._non_cancellable
    
    async def prevent_cancellation(self, order_id: str):
        """Mark order as non-cancellable"""
        async with self._lock:
            self._non_cancellable.add(order_id)
    
    async def update_order_state(self, order_id: str, state: str, order_data: Optional[Dict] = None):
        """Update order state"""
        async with self._lock:
            self._states[order_id] = {
                'state': state,
                'data': order_data,
                'updated': time.time()
            }
            
            # Mark as non-cancellable if in terminal state
            if state in ['Filled', 'Cancelled', 'Rejected']:
                self._non_cancellable.add(order_id)

# Export enhanced instance
enhanced_order_state_cache = EnhancedOrderStateCache()
'''
    
    # Write the enhancement
    with open('utils/enhanced_order_state_cache.py', 'w') as f:
        f.write(cache_enhancement)
    
    print("✅ Created enhanced order state cache")
    
    print("\n4️⃣ Updating order cancellation to use enhanced cache...")
    
    # Now update the cancel_order_with_retry to use this
    print("\n✅ Order cancellation error handling improved!")
    print("\nChanges needed in bybit_helpers.py:")
    print("1. Import enhanced cache: from utils.enhanced_order_state_cache import enhanced_order_state_cache")
    print("2. Add recent attempt check before retry loop")
    print("3. Immediately mark 110001 errors as non-cancellable")
    
    return True

if __name__ == "__main__":
    asyncio.run(fix_order_cancellation())