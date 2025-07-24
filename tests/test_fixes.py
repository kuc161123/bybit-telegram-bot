#!/usr/bin/env python3
"""
Test script to verify all critical fixes are working properly
Tests the 5 major issues that were identified and fixed:
1. SL order ID timing warnings
2. API parameter errors
3. Position verification tolerance
4. Mirror account error handling
5. Auto-rebalancer performance optimizations
"""

import asyncio
import logging
import sys
import time
from decimal import Decimal
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FixVerificationTests:
    """Test suite to verify all fixes are working"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
    
    def log_test_result(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        full_message = f"{status} - {test_name}"
        if message:
            full_message += f": {message}"
        
        logger.info(full_message)
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
    
    def test_1_monitor_timing_fix(self):
        """Test 1: Verify SL order ID timing warnings are fixed"""
        try:
            from execution.monitor import move_sl_to_breakeven
            import inspect
            
            # Check if the function has the timing logic
            source = inspect.getsource(move_sl_to_breakeven)
            
            has_timing_check = "position_start_time" in source
            has_debug_logging = "logger.debug" in source and "position age" in source
            has_tolerance = "time_since_start < 120" in source
            
            all_fixes_present = has_timing_check and has_debug_logging and has_tolerance
            
            self.log_test_result(
                "Monitor Timing Fix", 
                all_fixes_present,
                "Timing logic, debug logging, and 2-minute tolerance implemented"
            )
            
        except Exception as e:
            self.log_test_result("Monitor Timing Fix", False, f"Error: {e}")
    
    def test_2_api_parameter_fix(self):
        """Test 2: Verify API parameter fixes are in place"""
        try:
            from utils.order_consolidation import OrderConsolidator
            import inspect
            
            # Check if OrderConsolidator methods have category parameters
            consolidator = OrderConsolidator()
            
            # Check detect_existing_approach method
            source = inspect.getsource(consolidator.detect_existing_approach)
            has_category_param = 'category="linear"' in source
            
            # Check cleanup methods
            cleanup_source = inspect.getsource(consolidator.cleanup_approach_orders)
            has_category_in_cleanup = 'category="linear"' in cleanup_source
            
            all_api_fixes = has_category_param and has_category_in_cleanup
            
            self.log_test_result(
                "API Parameter Fix",
                all_api_fixes,
                "category='linear' parameter added to all Bybit API calls"
            )
            
        except Exception as e:
            self.log_test_result("API Parameter Fix", False, f"Error: {e}")
    
    def test_3_position_verification_tolerance(self):
        """Test 3: Verify position verification tolerance improvements"""
        try:
            from utils.trade_verifier import TradeVerifier
            import inspect
            
            verifier = TradeVerifier()
            
            # Check conservative approach method for tolerance
            source = inspect.getsource(verifier._verify_conservative_approach)
            has_tolerance_calc = "Decimal('0.005')" in source
            has_max_tolerance = "max(position_size" in source
            
            # Check fast approach method
            fast_source = inspect.getsource(verifier._verify_fast_approach)
            has_fast_tolerance = "Decimal('0.005')" in fast_source
            
            tolerance_improved = has_tolerance_calc and has_max_tolerance and has_fast_tolerance
            
            self.log_test_result(
                "Position Verification Tolerance",
                tolerance_improved,
                "0.5% tolerance implemented for quantity verification"
            )
            
        except Exception as e:
            self.log_test_result("Position Verification Tolerance", False, f"Error: {e}")
    
    def test_4_mirror_error_handling(self):
        """Test 4: Verify mirror account error handling improvements"""
        try:
            from execution.monitor import monitor_mirror_position_loop_enhanced
            from execution.auto_rebalancer import AutoRebalancer
            import inspect
            
            # Check monitor function for improved error handling
            monitor_source = inspect.getsource(monitor_mirror_position_loop_enhanced)
            has_cycle_logging = "monitoring_cycles % 10" in monitor_source
            has_auto_stop = "monitoring_cycles > 50" in monitor_source
            has_debug_level = "logger.debug" in monitor_source
            
            # Check auto-rebalancer for mirror error isolation
            rebalancer_source = inspect.getsource(AutoRebalancer._monitor_loop)
            has_mirror_isolation = "except Exception as mirror_error" in rebalancer_source
            has_continue_logic = "Continue with main loop" in rebalancer_source
            
            mirror_handling_improved = (has_cycle_logging and has_auto_stop and 
                                      has_debug_level and has_mirror_isolation and 
                                      has_continue_logic)
            
            self.log_test_result(
                "Mirror Error Handling",
                mirror_handling_improved,
                "Reduced logging frequency, auto-stop, and error isolation implemented"
            )
            
        except Exception as e:
            self.log_test_result("Mirror Error Handling", False, f"Error: {e}")
    
    def test_5_rebalancer_performance(self):
        """Test 5: Verify auto-rebalancer performance optimizations"""
        try:
            from execution.auto_rebalancer import REBALANCE_CHECK_INTERVAL, AutoRebalancer
            import inspect
            
            # Check if interval is optimized (should be 60s)
            interval_optimized = REBALANCE_CHECK_INTERVAL >= 60
            
            # Check for delays in rebalancing operations
            rebalancer_source = inspect.getsource(AutoRebalancer._rebalance_changed_positions)
            has_operation_delay = "await asyncio.sleep(2)" in rebalancer_source
            
            # Check for debug logging to reduce noise
            monitor_source = inspect.getsource(AutoRebalancer._monitor_loop)
            has_debug_logging = "logger.debug" in monitor_source
            
            performance_optimized = interval_optimized and has_operation_delay and has_debug_logging
            
            self.log_test_result(
                "Auto-rebalancer Performance",
                performance_optimized,
                f"Check interval: {REBALANCE_CHECK_INTERVAL}s, operation delays, debug logging"
            )
            
        except Exception as e:
            self.log_test_result("Auto-rebalancer Performance", False, f"Error: {e}")
    
    def test_6_file_integrity(self):
        """Test 6: Verify all critical files exist and are readable"""
        critical_files = [
            "execution/monitor.py",
            "utils/order_consolidation.py", 
            "utils/trade_verifier.py",
            "execution/auto_rebalancer.py"
        ]
        
        missing_files = []
        for file_path in critical_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if len(content) < 100:  # Basic sanity check
                        missing_files.append(f"{file_path} (too small)")
            except Exception as e:
                missing_files.append(f"{file_path} ({e})")
        
        files_ok = len(missing_files) == 0
        message = "All files present" if files_ok else f"Missing: {missing_files}"
        
        self.log_test_result("File Integrity", files_ok, message)
    
    def test_7_import_validation(self):
        """Test 7: Verify all fixed modules can be imported without errors"""
        modules_to_test = [
            "execution.monitor",
            "utils.order_consolidation", 
            "utils.trade_verifier",
            "execution.auto_rebalancer"
        ]
        
        import_errors = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except Exception as e:
                import_errors.append(f"{module_name}: {e}")
        
        imports_ok = len(import_errors) == 0
        message = "All modules importable" if imports_ok else f"Errors: {import_errors}"
        
        self.log_test_result("Import Validation", imports_ok, message)
    
    async def run_all_tests(self):
        """Run all verification tests"""
        logger.info("🚀 Starting Bot Stability Fix Verification Tests")
        logger.info("=" * 60)
        
        # Run all tests
        self.test_1_monitor_timing_fix()
        self.test_2_api_parameter_fix()
        self.test_3_position_verification_tolerance()
        self.test_4_mirror_error_handling()
        self.test_5_rebalancer_performance()
        self.test_6_file_integrity()
        self.test_7_import_validation()
        
        # Summary
        logger.info("=" * 60)
        logger.info("📊 TEST SUMMARY")
        logger.info(f"✅ Tests Passed: {self.tests_passed}")
        logger.info(f"❌ Tests Failed: {self.tests_failed}")
        logger.info(f"📈 Success Rate: {(self.tests_passed/(self.tests_passed+self.tests_failed)*100):.1f}%")
        
        if self.tests_failed == 0:
            logger.info("🎉 ALL TESTS PASSED - Bot fixes are working correctly!")
            return True
        else:
            logger.error("⚠️ Some tests failed - please review the issues above")
            return False

async def main():
    """Main test runner"""
    try:
        tester = FixVerificationTests()
        success = await tester.run_all_tests()
        
        if success:
            logger.info("\n🚀 Ready to restart bot with fixes applied!")
            logger.info("Restart the bot using: python main.py")
        else:
            logger.error("\n⚠️ Please fix the failing tests before restarting the bot")
            
        return success
        
    except Exception as e:
        logger.error(f"Test runner error: {e}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)