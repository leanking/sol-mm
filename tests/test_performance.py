#!/usr/bin/env python3
"""
Performance tests for the market making system.
Validates performance optimizations and measures improvements.
"""

import unittest
import sys
import os
import time
import json
import statistics
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import ConfigManager
from logger import MarketMakerLogger
from exchange import HyperliquidExchange
from strategy import MarketMakingStrategy
from volatility import VolatilityCalculator
from risk_manager import RiskManager
from performance_optimizer import PerformanceOptimizer
from main import MarketMaker

class TestPerformanceOptimizations(unittest.TestCase):
    """Performance optimization tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.config = ConfigManager()
        cls.logger = MarketMakerLogger()
        cls.exchange = HyperliquidExchange(cls.config, cls.logger)
        
        # Connect to exchange
        if not cls.exchange.connect():
            raise Exception("Failed to connect to Hyperliquid for performance tests")
        
        # Initialize components
        cls.volatility = VolatilityCalculator(cls.config, cls.logger)
        cls.risk = RiskManager(cls.config, cls.logger)
        cls.strategy = MarketMakingStrategy(
            cls.config, cls.exchange, cls.volatility, cls.risk, cls.logger
        )
        
        # Create market maker instance
        cls.market_maker = MarketMaker("config.json")
        
        # Performance test results
        cls.performance_results = {
            'price_updates': [],
            'order_execution': [],
            'volatility_calculations': [],
            'cache_performance': [],
            'overall_cycle_times': []
        }
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        if hasattr(cls, 'logger'):
            cls.logger.cleanup()
        if hasattr(cls, 'market_maker') and hasattr(cls.market_maker, 'components'):
            if 'logger' in cls.market_maker.components:
                cls.market_maker.components['logger'].cleanup()
    
    def test_01_price_update_performance(self):
        """Test price update performance with caching."""
        print("📈 Testing price update performance...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Test without caching (first call)
        times_without_cache = []
        for _ in range(10):
            start_time = time.time()
            ticker = self.exchange.get_ticker(spot_symbol)
            duration = time.time() - start_time
            times_without_cache.append(duration)
            time.sleep(0.1)  # Small delay
        
        # Test with caching (subsequent calls)
        times_with_cache = []
        for _ in range(10):
            start_time = time.time()
            ticker = self.exchange.get_ticker(spot_symbol)
            duration = time.time() - start_time
            times_with_cache.append(duration)
            time.sleep(0.01)  # Shorter delay for cached calls
        
        # Calculate statistics
        avg_without_cache = statistics.mean(times_without_cache)
        avg_with_cache = statistics.mean(times_with_cache)
        
        # Store results
        self.performance_results['price_updates'].append({
            'without_cache': avg_without_cache,
            'with_cache': avg_with_cache,
            'improvement': (avg_without_cache - avg_with_cache) / avg_without_cache * 100
        })
        
        # Assertions
        self.assertLess(avg_with_cache, avg_without_cache, 
                       f"Cached calls should be faster: {avg_with_cache:.3f}s vs {avg_without_cache:.3f}s")
        
        improvement = (avg_without_cache - avg_with_cache) / avg_without_cache * 100
        self.assertGreater(improvement, 50, f"Cache should provide >50% improvement, got {improvement:.1f}%")
        
        print(f"✅ Price update performance: {avg_without_cache:.3f}s -> {avg_with_cache:.3f}s "
              f"({improvement:.1f}% improvement)")
    
    def test_02_order_execution_performance(self):
        """Test order execution and cancellation performance."""
        print("📋 Testing order execution performance...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Test order placement performance
        placement_times = []
        order_ids = []
        
        for i in range(5):  # Test 5 orders
            start_time = time.time()
            order_id = self.exchange.place_order(
                spot_symbol, 'buy', 0.1, 100.0, 'limit', 'spot'
            )
            duration = time.time() - start_time
            placement_times.append(duration)
            
            if order_id:
                order_ids.append(order_id)
            
            time.sleep(0.1)
        
        # Test order cancellation performance
        cancellation_times = []
        for order_id in order_ids:
            start_time = time.time()
            success = self.exchange.cancel_order(order_id, spot_symbol, 'spot')
            duration = time.time() - start_time
            cancellation_times.append(duration)
            time.sleep(0.1)
        
        # Calculate statistics
        avg_placement_time = statistics.mean(placement_times) if placement_times else 0
        avg_cancellation_time = statistics.mean(cancellation_times) if cancellation_times else 0
        
        # Store results
        self.performance_results['order_execution'].append({
            'placement_time': avg_placement_time,
            'cancellation_time': avg_cancellation_time,
            'total_orders': len(order_ids)
        })
        
        # Assertions
        self.assertLess(avg_placement_time, 2.0, f"Order placement should be <2s, got {avg_placement_time:.3f}s")
        self.assertLess(avg_cancellation_time, 1.0, f"Order cancellation should be <1s, got {avg_cancellation_time:.3f}s")
        
        print(f"✅ Order execution performance: Placement {avg_placement_time:.3f}s, "
              f"Cancellation {avg_cancellation_time:.3f}s")
    
    def test_03_volatility_calculation_performance(self):
        """Test volatility calculation performance with caching."""
        print("📊 Testing volatility calculation performance...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Test ATR calculation performance
        atr_times = []
        for _ in range(5):
            start_time = time.time()
            atr = self.volatility.calculate_atr(spot_symbol, 14, '1h')
            duration = time.time() - start_time
            atr_times.append(duration)
            time.sleep(0.1)
        
        # Test volatility calculation performance
        vol_times = []
        for _ in range(5):
            start_time = time.time()
            volatility = self.volatility.calculate_volatility(spot_symbol, 14, '1h')
            duration = time.time() - start_time
            vol_times.append(duration)
            time.sleep(0.1)
        
        # Calculate statistics
        avg_atr_time = statistics.mean(atr_times) if atr_times else 0
        avg_vol_time = statistics.mean(vol_times) if vol_times else 0
        
        # Store results
        self.performance_results['volatility_calculations'].append({
            'atr_time': avg_atr_time,
            'volatility_time': avg_vol_time
        })
        
        # Assertions
        self.assertLess(avg_atr_time, 1.0, f"ATR calculation should be <1s, got {avg_atr_time:.3f}s")
        self.assertLess(avg_vol_time, 1.5, f"Volatility calculation should be <1.5s, got {avg_vol_time:.3f}s")
        
        print(f"✅ Volatility calculation performance: ATR {avg_atr_time:.3f}s, "
              f"Volatility {avg_vol_time:.3f}s")
    
    def test_04_cache_performance(self):
        """Test cache hit rates and effectiveness."""
        print("💾 Testing cache performance...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Clear caches
        self.exchange.clear_performance_cache()
        self.volatility.clear_cache()
        
        # Perform operations to populate cache
        for _ in range(5):
            self.exchange.get_ticker(spot_symbol)
            self.volatility.calculate_volatility(spot_symbol, 14, '1h')
            time.sleep(0.1)
        
        # Test cache hit rates
        cache_hit_times = []
        for _ in range(10):
            start_time = time.time()
            self.exchange.get_ticker(spot_symbol)
            duration = time.time() - start_time
            cache_hit_times.append(duration)
            time.sleep(0.01)
        
        # Get cache statistics
        exchange_stats = self.exchange.get_performance_stats()
        volatility_stats = self.volatility.get_cache_stats()
        
        avg_cache_hit_time = statistics.mean(cache_hit_times) if cache_hit_times else 0
        
        # Store results
        self.performance_results['cache_performance'].append({
            'cache_hit_time': avg_cache_hit_time,
            'volatility_hit_rate': volatility_stats.get('hit_rate', 0),
            'exchange_api_calls': exchange_stats.get('api_call_count', 0)
        })
        
        # Assertions
        self.assertLess(avg_cache_hit_time, 0.01, f"Cache hits should be <10ms, got {avg_cache_hit_time:.3f}s")
        self.assertGreater(volatility_stats.get('hit_rate', 0), 50, 
                          f"Volatility cache hit rate should be >50%, got {volatility_stats.get('hit_rate', 0):.1f}%")
        
        print(f"✅ Cache performance: Hit time {avg_cache_hit_time:.3f}s, "
              f"Volatility hit rate {volatility_stats.get('hit_rate', 0):.1f}%")
    
    def test_05_strategy_cycle_performance(self):
        """Test complete strategy cycle performance."""
        print("🔄 Testing strategy cycle performance...")
        
        # Test multiple strategy cycles
        cycle_times = []
        successful_cycles = 0
        
        for i in range(5):
            start_time = time.time()
            try:
                result = self.strategy.execute_strategy_cycle()
                duration = time.time() - start_time
                cycle_times.append(duration)
                
                if result['success']:
                    successful_cycles += 1
                
                time.sleep(1)  # Wait between cycles
                
            except Exception as e:
                print(f"Cycle {i+1} failed: {e}")
                continue
        
        # Calculate statistics
        avg_cycle_time = statistics.mean(cycle_times) if cycle_times else 0
        max_cycle_time = max(cycle_times) if cycle_times else 0
        
        # Store results
        self.performance_results['overall_cycle_times'].append({
            'avg_cycle_time': avg_cycle_time,
            'max_cycle_time': max_cycle_time,
            'successful_cycles': successful_cycles,
            'total_cycles': len(cycle_times)
        })
        
        # Assertions
        self.assertGreater(successful_cycles, 0, "At least one cycle should succeed")
        self.assertLess(avg_cycle_time, 5.0, f"Average cycle time should be <5s, got {avg_cycle_time:.3f}s")
        self.assertLess(max_cycle_time, 10.0, f"Max cycle time should be <10s, got {max_cycle_time:.3f}s")
        
        success_rate = (successful_cycles / len(cycle_times) * 100) if cycle_times else 0
        print(f"✅ Strategy cycle performance: Avg {avg_cycle_time:.3f}s, "
              f"Max {max_cycle_time:.3f}s, Success rate {success_rate:.1f}%")
    
    def test_06_rate_limiting_effectiveness(self):
        """Test rate limiting and API call spacing."""
        print("⏱️  Testing rate limiting effectiveness...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Test rapid API calls
        rapid_call_times = []
        for _ in range(10):
            start_time = time.time()
            self.exchange.get_ticker(spot_symbol)
            duration = time.time() - start_time
            rapid_call_times.append(duration)
            # No sleep - test rate limiting
        
        # Calculate statistics
        avg_rapid_time = statistics.mean(rapid_call_times) if rapid_call_times else 0
        
        # Check if rate limiting is working
        rate_limited_calls = sum(1 for t in rapid_call_times if t > 0.05)
        
        # Store results
        self.performance_results['rate_limiting'] = {
            'avg_rapid_call_time': avg_rapid_time,
            'rate_limited_calls': rate_limited_calls,
            'total_calls': len(rapid_call_times)
        }
        
        # Assertions
        self.assertGreater(rate_limited_calls, 0, "Rate limiting should be active")
        
        print(f"✅ Rate limiting: {rate_limited_calls}/{len(rapid_call_times)} calls were rate limited")
    
    def test_07_performance_optimization_recommendations(self):
        """Test performance optimization recommendations."""
        print("🎯 Testing performance optimization recommendations...")
        
        # Get performance statistics
        exchange_stats = self.exchange.get_performance_stats()
        volatility_stats = self.volatility.get_cache_stats()
        
        # Get recommendations
        optimizer = self.exchange.performance_optimizer
        recommendations = optimizer.get_recommendations()
        
        # Store results
        self.performance_results['recommendations'] = {
            'recommendations': recommendations,
            'slow_operations': exchange_stats.get('slow_operations', []),
            'api_call_count': exchange_stats.get('api_call_count', 0)
        }
        
        # Log recommendations
        if recommendations:
            print("Performance recommendations:")
            for rec in recommendations:
                print(f"  - {rec}")
        else:
            print("No performance recommendations - system is optimized")
        
        # Assertions
        self.assertIsInstance(recommendations, list, "Recommendations should be a list")
        
        print("✅ Performance recommendations generated")
    
    def test_08_performance_summary(self):
        """Generate comprehensive performance summary."""
        print("\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)
        
        # Calculate overall statistics
        total_tests = 0
        passed_tests = 0
        
        # Price update performance
        if self.performance_results['price_updates']:
            price_result = self.performance_results['price_updates'][0]
            improvement = price_result['improvement']
            print(f"📈 Price Updates: {improvement:.1f}% improvement with caching")
            total_tests += 1
            if improvement > 50:
                passed_tests += 1
        
        # Order execution performance
        if self.performance_results['order_execution']:
            order_result = self.performance_results['order_execution'][0]
            placement_time = order_result['placement_time']
            cancellation_time = order_result['cancellation_time']
            print(f"📋 Order Execution: Placement {placement_time:.3f}s, Cancellation {cancellation_time:.3f}s")
            total_tests += 1
            if placement_time < 2.0 and cancellation_time < 1.0:
                passed_tests += 1
        
        # Volatility calculation performance
        if self.performance_results['volatility_calculations']:
            vol_result = self.performance_results['volatility_calculations'][0]
            atr_time = vol_result['atr_time']
            vol_time = vol_result['volatility_time']
            print(f"📊 Volatility Calculations: ATR {atr_time:.3f}s, Volatility {vol_time:.3f}s")
            total_tests += 1
            if atr_time < 1.0 and vol_time < 1.5:
                passed_tests += 1
        
        # Cache performance
        if self.performance_results['cache_performance']:
            cache_result = self.performance_results['cache_performance'][0]
            hit_time = cache_result['cache_hit_time']
            hit_rate = cache_result['volatility_hit_rate']
            print(f"💾 Cache Performance: Hit time {hit_time:.3f}s, Hit rate {hit_rate:.1f}%")
            total_tests += 1
            if hit_time < 0.01 and hit_rate > 50:
                passed_tests += 1
        
        # Overall cycle performance
        if self.performance_results['overall_cycle_times']:
            cycle_result = self.performance_results['overall_cycle_times'][0]
            avg_time = cycle_result['avg_cycle_time']
            success_rate = (cycle_result['successful_cycles'] / cycle_result['total_cycles'] * 100)
            print(f"🔄 Strategy Cycles: Avg {avg_time:.3f}s, Success rate {success_rate:.1f}%")
            total_tests += 1
            if avg_time < 5.0 and success_rate > 50:
                passed_tests += 1
        
        # Performance score
        performance_score = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{'='*60}")
        print("PERFORMANCE ASSESSMENT")
        print(f"{'='*60}")
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {total_tests - passed_tests} ❌")
        print(f"Performance score: {performance_score:.1f}%")
        
        # Provide recommendations
        if performance_score >= 90:
            print("\n🎉 EXCELLENT! Performance optimizations are working effectively.")
            print("   - All critical performance metrics are within acceptable ranges")
            print("   - Caching and rate limiting are functioning properly")
            print("   - System is ready for production use")
        elif performance_score >= 75:
            print("\n✅ GOOD! Performance is mostly optimized.")
            print("   - Most performance metrics are acceptable")
            print("   - Consider reviewing failed metrics for further optimization")
        else:
            print("\n⚠️  NEEDS IMPROVEMENT! Performance optimizations need attention.")
            print("   - Several performance metrics are outside acceptable ranges")
            print("   - Review and address the failed metrics")
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"performance_test_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'performance_score': performance_score,
                'results': self.performance_results
            }, f, indent=2)
        
        print(f"\n📄 Performance results saved to: {results_file}")
        
        # Final assertion
        self.assertGreaterEqual(performance_score, 75, 
                               f"Performance score should be >=75%, got {performance_score:.1f}%")


if __name__ == '__main__':
    # Run performance tests
    unittest.main(verbosity=2) 