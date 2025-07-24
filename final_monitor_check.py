import pickle

# Load monitors from pickle
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})

print("="*80)
print("FINAL MONITOR STATUS REPORT")
print("="*80)

# Expected positions based on exchange data
expected_positions = {
    'main': ['ONTUSDT_Buy_main', 'SNXUSDT_Buy_main', 'SOLUSDT_Buy_main'],
    'mirror': ['ONTUSDT_Buy_mirror', 'SNXUSDT_Buy_mirror', 'SOLUSDT_Buy_mirror']
}

all_expected = expected_positions['main'] + expected_positions['mirror']
actual_monitors = list(monitors.keys())

print(f"\n📊 SUMMARY:")
print(f"  • Total positions on exchange: {len(all_expected)} (3 main + 3 mirror)")
print(f"  • Total monitors in pickle: {len(actual_monitors)}")

print(f"\n📈 CURRENT MONITORS:")
for key in sorted(actual_monitors):
    monitor = monitors[key]
    print(f"  ✓ {key}: Size={monitor.get('position_size', 0)}")

print(f"\n❌ MISSING MONITORS:")
missing = []
for pos in all_expected:
    if pos not in actual_monitors:
        missing.append(pos)
        print(f"  • {pos}")

print(f"\n⚠️  ORPHANED MONITORS (monitor exists but position size mismatch):")
# Check SOLUSDT_Buy_mirror specifically
if 'SOLUSDT_Buy_mirror' in monitors:
    monitor_size = float(monitors['SOLUSDT_Buy_mirror'].get('position_size', 0))
    print(f"  • SOLUSDT_Buy_mirror: Monitor shows {monitor_size} but exchange shows 4.1")

print(f"\n📊 FINAL ANALYSIS:")
print(f"  • Missing monitors: {len(missing)}")
print(f"  • Monitors needing update: 1 (SOLUSDT_Buy_mirror size mismatch)")
print(f"  • Total corrections needed: {len(missing) + 1}")
