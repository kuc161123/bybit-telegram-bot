#!/usr/bin/env python3
"""
Comprehensive Position Analysis
==============================

Analyze all positions on main and mirror accounts to detect:
1. Positions with TP fills that aren't detected
2. Monitors in wrong phase
3. Inconsistent state between accounts
4. Root causes of TP detection failures
"""
import pickle
from decimal import Decimal
import json

def analyze_all_positions():
    """Comprehensive analysis of all positions"""
    print("🔍 COMPREHENSIVE POSITION ANALYSIS")
    print("="*60)
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Total Enhanced TP/SL Monitors: {len(enhanced_monitors)}")
        
        # Group monitors by symbol
        position_groups = {}
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            if symbol not in position_groups:
                position_groups[symbol] = {}
            position_groups[symbol][account] = {
                'key': monitor_key,
                'data': monitor_data
            }
        
        print(f"🎯 Unique Symbols: {len(position_groups)}")
        
        # Analyze each position group
        issues_found = []
        
        for symbol, accounts in position_groups.items():
            print(f"\n{'='*60}")
            print(f"📈 ANALYZING: {symbol}")
            print(f"{'='*60}")
            
            main_account = accounts.get('main')
            mirror_account = accounts.get('mirror')
            
            if main_account:
                main_issues = analyze_single_position(symbol, 'main', main_account)
                issues_found.extend(main_issues)
            
            if mirror_account:
                mirror_issues = analyze_single_position(symbol, 'mirror', mirror_account)
                issues_found.extend(mirror_issues)
            
            # Cross-account analysis
            if main_account and mirror_account:
                cross_issues = analyze_cross_account_consistency(symbol, main_account, mirror_account)
                issues_found.extend(cross_issues)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 ANALYSIS SUMMARY")
        print(f"{'='*60}")
        print(f"🎯 Total Positions Analyzed: {len(position_groups)}")
        print(f"❌ Issues Found: {len(issues_found)}")
        
        if issues_found:
            print(f"\n🚨 ISSUES DETECTED:")
            for i, issue in enumerate(issues_found, 1):
                print(f"{i}. {issue}")
        else:
            print(f"\n✅ No issues detected!")
        
        # Root cause analysis
        analyze_root_causes(issues_found)
        
        return issues_found
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return []

def analyze_single_position(symbol, account, account_data):
    """Analyze a single position for issues"""
    monitor_key = account_data['key']
    monitor_data = account_data['data']
    issues = []
    
    print(f"\n🔍 {account.upper()} Account Analysis:")
    
    # Basic info
    total_size = Decimal(str(monitor_data.get('position_size', '0')))
    remaining_size = Decimal(str(monitor_data.get('remaining_size', '0')))
    filled_amount = total_size - remaining_size
    
    tp1_hit = monitor_data.get('tp1_hit', False)
    phase = monitor_data.get('phase', 'UNKNOWN')
    filled_tps = monitor_data.get('filled_tps', [])
    
    print(f"   📊 Size: {total_size} | Remaining: {remaining_size} | Filled: {filled_amount}")
    print(f"   🎯 TP1 Hit: {tp1_hit} | Phase: {phase} | Filled TPs: {filled_tps}")
    
    # Issue 1: TP fills not detected
    if filled_amount > 0 and not tp1_hit:
        tp_orders = monitor_data.get('tp_orders', {})
        
        # Calculate expected TP1 size
        tp1_size = Decimal('0')
        for order_id, order_info in tp_orders.items():
            if order_info.get('tp_number') == 1:
                tp1_size = Decimal(str(order_info.get('quantity', '0')))
                break
        
        if filled_amount >= tp1_size * Decimal('0.95'):  # 95% tolerance
            issue = f"❌ {symbol} {account}: TP fills not detected (filled: {filled_amount}, tp1_size: {tp1_size})"
            issues.append(issue)
            print(f"   {issue}")
    
    # Issue 2: Wrong phase for amount filled
    if filled_amount > 0 and phase not in ['PROFIT_TAKING', 'POSITION_CLOSED']:
        issue = f"❌ {symbol} {account}: Wrong phase '{phase}' for filled amount {filled_amount}"
        issues.append(issue)
        print(f"   {issue}")
    
    # Issue 3: Inconsistent filled_tps vs tp1_hit
    if tp1_hit and 1 not in filled_tps:
        issue = f"❌ {symbol} {account}: tp1_hit=True but 1 not in filled_tps {filled_tps}"
        issues.append(issue)
        print(f"   {issue}")
    
    # Issue 4: Phase transition time missing
    if tp1_hit and not monitor_data.get('phase_transition_time'):
        issue = f"⚠️ {symbol} {account}: Missing phase_transition_time despite tp1_hit=True"
        issues.append(issue)
        print(f"   {issue}")
    
    if not issues:
        print(f"   ✅ No issues detected")
    
    return issues

def analyze_cross_account_consistency(symbol, main_account, mirror_account):
    """Analyze consistency between main and mirror accounts"""
    issues = []
    
    print(f"\n🔄 Cross-Account Consistency:")
    
    main_data = main_account['data']
    mirror_data = mirror_account['data']
    
    main_tp1_hit = main_data.get('tp1_hit', False)
    mirror_tp1_hit = mirror_data.get('tp1_hit', False)
    
    main_phase = main_data.get('phase', 'UNKNOWN')
    mirror_phase = mirror_data.get('phase', 'UNKNOWN')
    
    main_filled = Decimal(str(main_data.get('position_size', '0'))) - Decimal(str(main_data.get('remaining_size', '0')))
    mirror_filled = Decimal(str(mirror_data.get('position_size', '0'))) - Decimal(str(mirror_data.get('remaining_size', '0')))
    
    print(f"   Main: tp1_hit={main_tp1_hit}, phase={main_phase}, filled={main_filled}")
    print(f"   Mirror: tp1_hit={mirror_tp1_hit}, phase={mirror_phase}, filled={mirror_filled}")
    
    # Mirror should generally follow main account for TP hits
    if main_tp1_hit and not mirror_tp1_hit and mirror_filled > 0:
        issue = f"⚠️ {symbol}: Main has TP1 hit but mirror doesn't (mirror filled: {mirror_filled})"
        issues.append(issue)
        print(f"   {issue}")
    
    if not issues:
        print(f"   ✅ Cross-account consistency OK")
    
    return issues

def analyze_root_causes(issues):
    """Analyze root causes of detected issues"""
    print(f"\n{'='*60}")
    print(f"🔍 ROOT CAUSE ANALYSIS")
    print(f"{'='*60}")
    
    if not issues:
        print("✅ No issues to analyze")
        return
    
    # Categorize issues
    tp_detection_failures = [i for i in issues if "TP fills not detected" in i]
    phase_inconsistencies = [i for i in issues if "Wrong phase" in i]
    state_inconsistencies = [i for i in issues if "tp1_hit=True but" in i]
    missing_timestamps = [i for i in issues if "Missing phase_transition_time" in i]
    cross_account_issues = [i for i in issues if "Main has TP1 hit but mirror" in i]
    
    print(f"📊 Issue Categories:")
    print(f"   TP Detection Failures: {len(tp_detection_failures)}")
    print(f"   Phase Inconsistencies: {len(phase_inconsistencies)}")
    print(f"   State Inconsistencies: {len(state_inconsistencies)}")
    print(f"   Missing Timestamps: {len(missing_timestamps)}")
    print(f"   Cross-Account Issues: {len(cross_account_issues)}")
    
    print(f"\n🔍 Likely Root Causes:")
    
    if tp_detection_failures:
        print(f"1. 🚨 Enhanced TP/SL Manager not running when fills occurred")
        print(f"   - Bot was shut down during TP fills")
        print(f"   - Monitoring loop wasn't active")
        print(f"   - Position size changes not detected")
    
    if phase_inconsistencies or state_inconsistencies:
        print(f"2. 🚨 Monitor state updates not persisting")
        print(f"   - Concurrent pickle access issues")
        print(f"   - Race conditions during updates")
        print(f"   - Background tasks overwriting changes")
    
    if missing_timestamps:
        print(f"3. ⚠️ Incomplete state transitions")
        print(f"   - Partial updates during failures")
        print(f"   - Exception handling gaps")
    
    if cross_account_issues:
        print(f"4. ⚠️ Mirror account synchronization issues")
        print(f"   - Different fill timing between accounts")
        print(f"   - Mirror monitoring delays")
    
    print(f"\n💡 Recommended Solutions:")
    print(f"1. Implement startup TP fill detection system")
    print(f"2. Add pickle locking mechanism")
    print(f"3. Create monitor state recovery system")
    print(f"4. Enhance cross-account synchronization")
    print(f"5. Add position state validation on bot startup")

if __name__ == "__main__":
    issues = analyze_all_positions()