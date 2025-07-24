# Add to shared/state.py or main.py initialization
def ensure_all_monitors_have_chat_id():
    """Ensure all monitors have chat_id set"""
    try:
        import pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        fixed = 0
        
        for monitor_key, monitor_data in monitors.items():
            if not monitor_data.get('chat_id'):
                monitor_data['chat_id'] = 5634913742
                fixed += 1
        
        if fixed > 0:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            print(f"✅ Fixed {fixed} monitors with missing chat_id")
    except:
        pass

# Call this on startup
ensure_all_monitors_have_chat_id()
