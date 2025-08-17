#!/usr/bin/env python3
"""
Transaction Manager
Provides rollback capability for trading operations
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class ActionType(Enum):
    """Types of actions that can be rolled back"""
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    MONITOR_CREATED = "monitor_created"
    MONITOR_DELETED = "monitor_deleted"
    POSITION_OPENED = "position_opened"
    POSITION_MODIFIED = "position_modified"
    STATE_CHANGED = "state_changed"

@dataclass
class TransactionAction:
    """Represents a single reversible action"""
    action_type: ActionType
    timestamp: datetime
    data: Dict[str, Any]
    rollback_func: Optional[callable] = None
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    rolled_back: bool = False

class Transaction:
    """
    Manages a transaction with multiple actions that can be rolled back
    """
    
    def __init__(self, name: str):
        """
        Initialize a new transaction
        
        Args:
            name: Transaction identifier
        """
        self.name = name
        self.actions: List[TransactionAction] = []
        self.start_time = datetime.now()
        self.committed = False
        self.rolled_back = False
        
    def add_action(self, 
                   action_type: ActionType,
                   data: Dict[str, Any],
                   rollback_func: Optional[callable] = None,
                   rollback_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Add an action to the transaction
        
        Args:
            action_type: Type of action
            data: Action data
            rollback_func: Function to call for rollback
            rollback_data: Data needed for rollback
        """
        action = TransactionAction(
            action_type=action_type,
            timestamp=datetime.now(),
            data=data,
            rollback_func=rollback_func,
            rollback_data=rollback_data or {}
        )
        self.actions.append(action)
        logger.debug(f"Transaction '{self.name}': Added {action_type.value} action")
    
    async def rollback(self) -> Dict[str, Any]:
        """
        Rollback all actions in reverse order
        
        Returns:
            Rollback results
        """
        if self.rolled_back:
            logger.warning(f"Transaction '{self.name}' already rolled back")
            return {'status': 'already_rolled_back'}
        
        if self.committed:
            logger.warning(f"Transaction '{self.name}' was committed, rollback may be incomplete")
        
        results = {
            'transaction': self.name,
            'actions_rolled_back': 0,
            'failures': []
        }
        
        # Rollback in reverse order
        for action in reversed(self.actions):
            if action.rolled_back:
                continue
            
            try:
                if action.rollback_func:
                    if asyncio.iscoroutinefunction(action.rollback_func):
                        await action.rollback_func(**action.rollback_data)
                    else:
                        action.rollback_func(**action.rollback_data)
                    
                    action.rolled_back = True
                    results['actions_rolled_back'] += 1
                    logger.info(f"Rolled back {action.action_type.value} in transaction '{self.name}'")
                else:
                    logger.debug(f"No rollback function for {action.action_type.value}")
                    
            except Exception as e:
                error_msg = f"Failed to rollback {action.action_type.value}: {e}"
                logger.error(error_msg)
                results['failures'].append(error_msg)
        
        self.rolled_back = True
        results['status'] = 'success' if not results['failures'] else 'partial'
        
        return results
    
    def commit(self) -> None:
        """Mark transaction as committed (successful completion)"""
        self.committed = True
        logger.info(f"Transaction '{self.name}' committed successfully")

class TransactionManager:
    """
    Manages multiple transactions
    """
    
    def __init__(self):
        self.transactions: Dict[str, Transaction] = {}
        self.current_transaction: Optional[Transaction] = None
        
    def begin_transaction(self, name: str) -> Transaction:
        """
        Begin a new transaction
        
        Args:
            name: Transaction name
            
        Returns:
            Transaction instance
        """
        if name in self.transactions:
            logger.warning(f"Transaction '{name}' already exists, creating new one")
        
        transaction = Transaction(name)
        self.transactions[name] = transaction
        self.current_transaction = transaction
        
        logger.info(f"Started transaction: {name}")
        return transaction
    
    def get_transaction(self, name: str) -> Optional[Transaction]:
        """Get a transaction by name"""
        return self.transactions.get(name)
    
    async def rollback_transaction(self, name: str) -> Dict[str, Any]:
        """
        Rollback a specific transaction
        
        Args:
            name: Transaction name
            
        Returns:
            Rollback results
        """
        transaction = self.transactions.get(name)
        if not transaction:
            logger.error(f"Transaction '{name}' not found")
            return {'status': 'not_found'}
        
        return await transaction.rollback()
    
    def commit_transaction(self, name: str) -> bool:
        """
        Commit a transaction
        
        Args:
            name: Transaction name
            
        Returns:
            True if successful
        """
        transaction = self.transactions.get(name)
        if not transaction:
            logger.error(f"Transaction '{name}' not found")
            return False
        
        transaction.commit()
        
        # Clear current if it matches
        if self.current_transaction == transaction:
            self.current_transaction = None
        
        return True
    
    async def rollback_all(self) -> Dict[str, Any]:
        """
        Rollback all uncommitted transactions
        
        Returns:
            Rollback results for all transactions
        """
        results = {}
        
        for name, transaction in self.transactions.items():
            if not transaction.committed:
                results[name] = await transaction.rollback()
        
        return results

# Global transaction manager
transaction_manager = TransactionManager()

# Helper functions for common rollback operations
async def create_order_rollback(order_id: str, symbol: str, client=None):
    """Rollback function to cancel an order"""
    try:
        from clients.bybit_helpers import cancel_order_with_retry
        await cancel_order_with_retry(
            symbol=symbol,
            order_id=order_id,
            client=client
        )
        logger.info(f"Rolled back order {order_id} for {symbol}")
    except Exception as e:
        logger.error(f"Failed to rollback order {order_id}: {e}")
        raise

async def create_monitor_rollback(monitor_key: str):
    """Rollback function to remove a monitor"""
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        if monitor_key in enhanced_tp_sl_manager.position_monitors:
            del enhanced_tp_sl_manager.position_monitors[monitor_key]
            logger.info(f"Rolled back monitor {monitor_key}")
    except Exception as e:
        logger.error(f"Failed to rollback monitor {monitor_key}: {e}")
        raise

def create_state_rollback(state_key: str, old_value: Any, context):
    """Rollback function to restore previous state"""
    try:
        if hasattr(context, 'chat_data') and state_key in context.chat_data:
            context.chat_data[state_key] = old_value
            logger.info(f"Rolled back state {state_key}")
    except Exception as e:
        logger.error(f"Failed to rollback state {state_key}: {e}")
        raise

# Context manager for automatic transaction handling
class TransactionContext:
    """Context manager for automatic transaction commit/rollback"""
    
    def __init__(self, name: str, auto_rollback: bool = True):
        """
        Initialize transaction context
        
        Args:
            name: Transaction name
            auto_rollback: Whether to automatically rollback on exception
        """
        self.name = name
        self.auto_rollback = auto_rollback
        self.transaction = None
        
    async def __aenter__(self):
        """Enter transaction context"""
        self.transaction = transaction_manager.begin_transaction(self.name)
        return self.transaction
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context"""
        if exc_type is not None and self.auto_rollback:
            # Exception occurred, rollback
            logger.warning(f"Exception in transaction '{self.name}', rolling back: {exc_val}")
            await self.transaction.rollback()
        elif exc_type is None:
            # Success, commit
            self.transaction.commit()
        
        # Don't suppress the exception
        return False