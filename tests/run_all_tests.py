#!/usr/bin/env python3
"""
Comprehensive test runner for the market making system.
Runs all tests including performance, integration, and production readiness tests.
"""

import unittest
import sys
import os
import time
import json
from datetime import datetime
from io import StringIO

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def run_test_suite(test_module, suite_name):
    """Run a specific test suite and return results.
    
    Args:
        test_module: The test module to run
        suite_name: Name of the test suite
        
    Returns:
        Dictionary with test results
    """
    print(f"\n{'='*60}")
    print(f"RUNNING {suite_name.upper()} TESTS")
    print(f"{'='*60}")
    
    # Capture test output
    test_output = StringIO()
    runner = unittest.TextTestRunner(stream=test_output, verbosity=2)
    
    # Load and run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_module)
    
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    # Parse results
    total_tests = result.testsRun
    failed_tests = len(result.failures)
    error_tests = len(result.errors)
    skipped_tests = len(result.skipped) if hasattr(result, 'skipped') else 0
    passed_tests = total_tests - failed_tests - error_tests - skipped_tests
    
    # Calculate success rate
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    # Get test output
    output = test_output.getvalue()
    test_output.close()
    
    return {
        'suite_name': suite_name,
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'error_tests': error_tests,
        'skipped_tests': skipped_tests,
        'success_rate': success_rate,
        'execution_time': end_time - start_time,
        'output': output,
        'failures': result.failures,
        'errors': result.errors
    }

def print_test_results(results):
    """Print formatted test results.
    
    Args:
        results: List of test result dictionaries
    """
    print(f"\n{'='*80}")
    print("COMPREHENSIVE TEST RESULTS SUMMARY")
    print(f"{'='*80}")
    
    total_suites = len(results)
    total_tests = sum(r['total_tests'] for r in results)
    total_passed = sum(r['passed_tests'] for r in results)
    total_failed = sum(r['failed_tests'] for r in results)
    total_errors = sum(r['error_tests'] for r in results)
    total_skipped = sum(r['skipped_tests'] for r in results)
    
    overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Test Suites: {total_suites}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed} ✅")
    print(f"Failed: {total_failed} ❌")
    print(f"Errors: {total_errors} ⚠️")
    print(f"Skipped: {total_skipped} ⏭️")
    print(f"Overall Success Rate: {overall_success_rate:.1f}%")
    
    print(f"\n{'='*80}")
    print("DETAILED RESULTS BY TEST SUITE")
    print(f"{'='*80}")
    
    for result in results:
        status_icon = "✅" if result['success_rate'] >= 90 else "⚠️" if result['success_rate'] >= 75 else "❌"
        
        print(f"\n{status_icon} {result['suite_name'].upper()}")
        print(f"   Tests: {result['total_tests']} | Passed: {result['passed_tests']} | "
              f"Failed: {result['failed_tests']} | Errors: {result['error_tests']} | "
              f"Skipped: {result['skipped_tests']}")
        print(f"   Success Rate: {result['success_rate']:.1f}% | "
              f"Execution Time: {result['execution_time']:.2f}s")
        
        # Show failures and errors
        if result['failures']:
            print(f"   Failures:")
            for test, traceback in result['failures']:
                print(f"     - {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result['errors']:
            print(f"   Errors:")
            for test, traceback in result['errors']:
                print(f"     - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    # Overall assessment
    print(f"\n{'='*80}")
    print("OVERALL ASSESSMENT")
    print(f"{'='*80}")
    
    if overall_success_rate >= 95:
        print("🎉 EXCELLENT! All test suites are performing well.")
        print("   - System is ready for production deployment")
        print("   - All critical functionality is working correctly")
        print("   - Performance optimizations are effective")
    elif overall_success_rate >= 85:
        print("✅ GOOD! Most test suites are passing.")
        print("   - System is mostly ready for production")
        print("   - Review failed tests for potential issues")
        print("   - Consider addressing any performance concerns")
    elif overall_success_rate >= 70:
        print("⚠️  FAIR! Some test suites need attention.")
        print("   - System needs improvement before production")
        print("   - Address failed tests and errors")
        print("   - Review performance optimizations")
    else:
        print("❌ POOR! Multiple test suites are failing.")
        print("   - System is not ready for production")
        print("   - Critical issues need to be resolved")
        print("   - Extensive testing and debugging required")
    
    return overall_success_rate

def save_test_results(results, overall_success_rate):
    """Save test results to a JSON file.
    
    Args:
        results: List of test result dictionaries
        overall_success_rate: Overall success rate
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"comprehensive_test_results_{timestamp}.json"
    
    # Prepare data for JSON serialization
    serializable_results = []
    for result in results:
        serializable_result = {
            'suite_name': result['suite_name'],
            'total_tests': result['total_tests'],
            'passed_tests': result['passed_tests'],
            'failed_tests': result['failed_tests'],
            'error_tests': result['error_tests'],
            'skipped_tests': result['skipped_tests'],
            'success_rate': result['success_rate'],
            'execution_time': result['execution_time'],
            'failures': [str(f[0]) for f in result['failures']],
            'errors': [str(e[0]) for e in result['errors']]
        }
        serializable_results.append(serializable_result)
    
    data = {
        'timestamp': timestamp,
        'overall_success_rate': overall_success_rate,
        'total_suites': len(results),
        'total_tests': sum(r['total_tests'] for r in results),
        'results': serializable_results
    }
    
    with open(results_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n📄 Comprehensive test results saved to: {results_file}")

def main():
    """Main test runner function."""
    print("🚀 STARTING COMPREHENSIVE MARKET MAKING SYSTEM TESTS")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Define test suites to run
    test_suites = [
        ('test_performance', 'Performance Optimizations'),
        ('test_integration', 'Integration'),
        ('test_strategy', 'Strategy'),
        ('test_production_readiness', 'Production Readiness'),
        ('test_paper_trading', 'Paper Trading'),
        ('test_stress', 'Stress Testing')
    ]
    
    results = []
    
    # Run each test suite
    for test_file, suite_name in test_suites:
        try:
            # Import test module
            test_module = __import__(test_file)
            
            # Run test suite
            result = run_test_suite(test_module, suite_name)
            results.append(result)
            
        except ImportError as e:
            print(f"⚠️  Could not import {test_file}: {e}")
            continue
        except Exception as e:
            print(f"❌ Error running {suite_name} tests: {e}")
            continue
    
    # Print comprehensive results
    overall_success_rate = print_test_results(results)
    
    # Save results
    save_test_results(results, overall_success_rate)
    
    # Exit with appropriate code
    if overall_success_rate >= 85:
        print(f"\n✅ Tests completed successfully (Success rate: {overall_success_rate:.1f}%)")
        sys.exit(0)
    else:
        print(f"\n❌ Tests completed with issues (Success rate: {overall_success_rate:.1f}%)")
        sys.exit(1)

if __name__ == '__main__':
    main() 