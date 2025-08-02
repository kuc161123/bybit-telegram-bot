#!/usr/bin/env python3

def create_monitor_tasks_helper():
    """Create a helper function to add to trader.py for monitor_tasks integration"""
    
    helper_code = '''
# Helper function for Enhanced TP/SL monitor_tasks integration
def create_enhanced_tp_sl_monitor_entry(application, symbol: str, side: str, chat_id: int, approach: str, account_type: str = "main"):
    """Create monitor_tasks entry for Enhanced TP/SL system"""
    try:
        if not application or not hasattr(application, 'bot_data'):
            logger.warning("No application context available for monitor_tasks creation")
            return
        
        bot_data = application.bot_data
        
        # Initialize monitor_tasks if not exists
        if 'monitor_tasks' not in bot_data:
            bot_data['monitor_tasks'] = {}
            logger.info("Created monitor_tasks in bot_data")
        
        # Create monitor key based on account type
        if account_type == "mirror":
            monitor_key = f"{chat_id}_{symbol}_{approach}_mirror"
            monitoring_mode = f"ENHANCED_TP_SL_MIRROR"
        else:
            monitor_key = f"{chat_id}_{symbol}_{approach}"
            monitoring_mode = f"ENHANCED_TP_SL"
        
        # Check if monitor already exists
        if monitor_key in bot_data['monitor_tasks']:
            existing_monitor = bot_data['monitor_tasks'][monitor_key]
            if existing_monitor.get('active', False):
                logger.info(f"Enhanced TP/SL monitor already exists and active: {monitor_key}")
                return
            # Reactivate existing monitor
            existing_monitor.update({
                'monitoring_mode': monitoring_mode,
                'started_at': time.time(),
                'active': True,
                'account_type': account_type,
                'system_type': 'enhanced_tp_sl'
            })
            logger.info(f"✅ Reactivated Enhanced TP/SL monitor: {monitor_key}")
        else:
            # Create new monitor
            bot_data['monitor_tasks'][monitor_key] = {
                'chat_id': chat_id,
                'symbol': symbol,
                'approach': approach.lower(),
                'monitoring_mode': monitoring_mode,
                'started_at': time.time(),
                'active': True,
                'account_type': account_type,
                'system_type': 'enhanced_tp_sl',
                'side': side  # Add side for hedge mode compatibility
            }
            logger.info(f"✅ Created Enhanced TP/SL monitor: {monitor_key}")
            
    except Exception as e:
        logger.error(f"Error creating Enhanced TP/SL monitor_tasks entry: {e}")
'''
    
    return helper_code

def create_integration_calls():
    """Create the integration calls to add after each Enhanced TP/SL setup"""
    
    integration_calls = {
        "fast_approach": '''
                # Create monitor_tasks entry for dashboard compatibility
                if enhanced_result.get("success"):
                    create_enhanced_tp_sl_monitor_entry(application, symbol, side, chat_id, "FAST", "main")
''',
        
        "conservative_approach": '''
                # Create monitor_tasks entry for dashboard compatibility  
                if enhanced_result.get("success"):
                    create_enhanced_tp_sl_monitor_entry(application, symbol, side, chat_id, "CONSERVATIVE", "main")
''',
        
        "ggshot_fast": '''
                # Create monitor_tasks entry for dashboard compatibility
                if enhanced_result.get("success"):
                    create_enhanced_tp_sl_monitor_entry(application, symbol, side, chat_id, "GGSHOT_FAST", "main")
''',
        
        "ggshot_conservative": '''
                # Create monitor_tasks entry for dashboard compatibility
                if enhanced_result.get("success"):
                    create_enhanced_tp_sl_monitor_entry(application, symbol, side, chat_id, "GGSHOT_CONSERVATIVE", "main")
'''
    }
    
    return integration_calls

def print_solution():
    """Print the complete solution for Enhanced TP/SL monitor integration"""
    
    print("🔧 ENHANCED TP/SL MONITOR INTEGRATION SOLUTION")
    print("="*70)
    
    print("\n1. ADD HELPER FUNCTION TO trader.py:")
    print("-" * 40)
    print("Add this helper function near the top of trader.py (after imports):")
    print()
    print(create_monitor_tasks_helper())
    
    print("\n2. ADD INTEGRATION CALLS:")
    print("-" * 30)
    print("Add these calls after each successful Enhanced TP/SL setup:")
    
    calls = create_integration_calls()
    for approach, call in calls.items():
        print(f"\n{approach.upper()}:")
        print(call)
    
    print("\n3. SPECIFIC LOCATIONS IN trader.py:")
    print("-" * 40)
    print("Line ~663: After fast approach enhanced_result")
    print("Line ~1917: After conservative approach enhanced_result") 
    print("Line ~2693: After GGShot fast enhanced_result")
    print("Line ~3108: After GGShot conservative enhanced_result")
    
    print("\n4. IMPORT REQUIREMENT:")
    print("-" * 25)
    print("Make sure 'time' is imported at the top of trader.py")
    
    print("\n🎯 RESULT:")
    print("="*70)
    print("✅ Enhanced TP/SL system will create monitor_tasks entries")
    print("✅ Dashboard Active Monitors will show correct counts") 
    print("✅ All trading approaches will be properly tracked")
    print("✅ Both main and mirror accounts supported")

if __name__ == "__main__":
    print_solution()