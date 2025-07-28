#!/usr/bin/env python3
"""
Clear dashboard cache and force fresh dashboard generation
"""
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def clear_dashboard_cache():
    """Clear all dashboard-related caches"""
    print("🔄 CLEARING DASHBOARD CACHE")
    print("=" * 40)
    
    try:
        # Import cache modules
        from utils.dashboard_cache import dashboard_cache
        from utils.cache import invalidate_all_caches
        
        # Clear dashboard-specific cache
        dashboard_cache.invalidate()
        print("✅ Dashboard cache cleared")
        
        # Clear general caches
        invalidate_all_caches()
        print("✅ All caches cleared")
        
        # Clear any cached component data
        try:
            from dashboard.lazy_components import lazy_loader
            if hasattr(lazy_loader, 'clear_cache'):
                lazy_loader.clear_cache()
                print("✅ Lazy component cache cleared")
        except Exception as e:
            print(f"⚠️ Could not clear lazy components: {e}")
        
        print("\n✅ Dashboard cache clearing complete!")
        print("💡 Your next dashboard request will be freshly generated")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing dashboard cache: {e}")
        return False

if __name__ == "__main__":
    clear_dashboard_cache()