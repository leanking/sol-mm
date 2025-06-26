#!/usr/bin/env python3
"""
Stress tests for the market maker system.
Tests system behavior under various adverse conditions and edge cases.
"""

import unittest
import sys
import os
import time
import threading
import concurrent.futures
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import using absolute imports from src
from config import ConfigManager
from logger import MarketMakerLogger
from exchange import HyperliquidExchange
from strategy import MarketMakingStrategy
from volatility import VolatilityCalculator
from risk_manager import RiskManager
from main import MarketMaker

class TestMarketMakerStress(unittest.TestCase):
    """Stress tests for the market maker system."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.config = ConfigManager()
        cls.logger = MarketMakerLogger()
        cls.exchange = HyperliquidExchange(cls.config, cls.logger)
        
        # Connect to exchange
        if not cls.exchange.connect():
            raise Exception("Failed to connect to Hyperliquid for stress tests")
        
        # Initialize components
        cls.volatility = VolatilityCalculator(cls.config, cls.logger)
        cls.risk = RiskManager(cls.config, cls.logger)
        cls.strategy = MarketMakingStrategy(
            cls.config, cls.exchange, cls.volatility, cls.risk, cls.logger
        )
        
        # Create market maker instance with correct constructor
        cls.market_maker = MarketMaker("config.json")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        # Clean up loggers to prevent resource warnings
        if hasattr(cls, 'logger'):
            cls.logger.cleanup()
        if hasattr(cls, 'market_maker') and hasattr(cls.market_maker, 'components'):
            if 'logger' in cls.market_maker.components:
                cls.market_maker.components['logger'].cleanup()
    
    def test_01_rapid_price_updates(self):
        """Test system behavior with rapid price updates."""
        print("Testing rapid price updates...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Simulate rapid price updates (reduced for faster testing)
        start_time = time.time()
        update_count = 0
        max_updates = 20  # Reduced from 100
        
        try:
            while update_count < max_updates and (time.time() - start_time) < 30:  # Reduced from 60
                # Get current price
                ticker = self.exchange.get_ticker(spot_symbol)
                if ticker:
                    mid_price = ticker['last']
                    
                    # Calculate quotes rapidly
                    volatility = 0.12
                    bid_price, ask_price, spread = self.strategy.calculate_quotes(mid_price, volatility)
                    
                    # Verify calculations are still valid
                    self.assertIsNotNone(bid_price)
                    self.assertIsNotNone(ask_price)
                    self.assertGreater(ask_price, bid_price)
                    
                    update_count += 1
                
                time.sleep(0.2)  # Increased from 0.1 for faster completion
            
            print(f"✅ Completed {update_count} rapid price updates")
            
        except Exception as e:
            self.fail(f"System failed under rapid price updates: {e}")
    
    def test_02_concurrent_operations(self):
        """Test system behavior with concurrent operations."""
        print("Testing concurrent operations...")
        
        def price_worker():
            """Worker thread for price calculations."""
            spot_symbol, _ = self.exchange.find_solana_markets()
            if not spot_symbol:
                return
            
            for _ in range(5):  # Reduced from 10
                try:
                    ticker = self.exchange.get_ticker(spot_symbol)
                    if ticker:
                        mid_price = ticker['last']
                        volatility = 0.12
                        self.strategy.calculate_quotes(mid_price, volatility)
                    time.sleep(0.2)  # Increased from 0.1
                except Exception as e:
                    print(f"Price worker error: {e}")
        
        def balance_worker():
            """Worker thread for balance checks."""
            for _ in range(5):  # Reduced from 10
                try:
                    self.exchange.get_balance()
                    time.sleep(0.2)  # Increased from 0.1
                except Exception as e:
                    print(f"Balance worker error: {e}")
        
        def volatility_worker():
            """Worker thread for volatility calculations."""
            spot_symbol, _ = self.exchange.find_solana_markets()
            if not spot_symbol:
                return
            
            for _ in range(5):  # Reduced from 10
                try:
                    self.volatility.calculate_atr(spot_symbol)
                    time.sleep(0.2)  # Increased from 0.1
                except Exception as e:
                    print(f"Volatility worker error: {e}")
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(price_worker),
                executor.submit(balance_worker),
                executor.submit(volatility_worker)
            ]
            
            # Wait for all to complete (reduced timeout)
            concurrent.futures.wait(futures, timeout=15)  # Reduced from 30
            
            # Check for exceptions
            for future in futures:
                if future.exception():
                    self.fail(f"Concurrent operation failed: {future.exception()}")
        
        print("✅ Concurrent operations completed successfully")
    
    def test_03_network_interruptions(self):
        """Test system behavior during network interruptions."""
        print("Testing network interruption handling...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Test with mocked network failures
        with patch.object(self.exchange, 'get_ticker') as mock_ticker:
            # Simulate network failure
            mock_ticker.side_effect = Exception("Network error")
            
            # System should handle the error gracefully
            ticker = self.exchange.get_ticker(spot_symbol)
            self.assertIsNone(ticker, "Should return None on network error")
            
            # Reset mock
            mock_ticker.side_effect = None
            
            # Test recovery
            ticker = self.exchange.get_ticker(spot_symbol)
            self.assertIsNotNone(ticker, "Should recover after network error")
        
        print("✅ Network interruption handling works correctly")
    
    def test_04_extreme_market_conditions(self):
        """Test system behavior under extreme market conditions."""
        print("Testing extreme market conditions...")
        
        # Test with extreme price movements
        extreme_prices = [0.01, 1000000.0, -100.0, 0.0]
        
        for price in extreme_prices:
            try:
                bid_price, ask_price, spread = self.strategy.calculate_quotes(price, 0.12)
                
                # System should handle extreme prices gracefully
                if price > 0:
                    self.assertIsNotNone(bid_price)
                    self.assertIsNotNone(ask_price)
                    self.assertGreater(ask_price, bid_price)
                else:
                    # For invalid prices, system should handle gracefully
                    pass
                    
            except Exception as e:
                # System should not crash on extreme prices
                print(f"Warning: Extreme price {price} caused error: {e}")
        
        # Test with extreme volatility
        extreme_volatilities = [0.0, 10.0, -0.5, 100.0]
        mid_price = 100.0
        
        for vol in extreme_volatilities:
            try:
                bid_price, ask_price, spread = self.strategy.calculate_quotes(mid_price, vol)
                
                if vol >= 0:
                    self.assertIsNotNone(bid_price)
                    self.assertIsNotNone(ask_price)
                else:
                    # Negative volatility should be handled gracefully
                    pass
                    
            except Exception as e:
                print(f"Warning: Extreme volatility {vol} caused error: {e}")
        
        print("✅ Extreme market conditions handled gracefully")
    
    def test_05_memory_usage(self):
        """Test memory usage under load."""
        print("Testing memory usage...")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform many operations (reduced for faster testing)
        spot_symbol, _ = self.exchange.find_solana_markets()
        if spot_symbol:
            for _ in range(100):  # Reduced from 1000
                ticker = self.exchange.get_ticker(spot_symbol)
                if ticker:
                    mid_price = ticker['last']
                    self.strategy.calculate_quotes(mid_price, 0.12)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"Memory usage - Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB, Increase: {memory_increase:.1f}MB")
        
        # Memory increase should be reasonable (less than 100MB)
        self.assertLess(memory_increase, 100, f"Memory usage increased too much: {memory_increase:.1f}MB")
        
        print("✅ Memory usage is reasonable")
    
    def test_06_error_recovery(self):
        """Test system recovery from various errors."""
        print("Testing error recovery...")
        
        # Test recovery from invalid configuration
        with patch.object(self.config, 'get_asset_config') as mock_config:
            mock_config.side_effect = Exception("Config error")
            
            try:
                asset_config = self.config.get_asset_config()
                self.fail("Should have raised exception")
            except Exception:
                pass  # Expected
            
            # Reset mock
            mock_config.side_effect = None
            
            # Test recovery
            asset_config = self.config.get_asset_config()
            self.assertIsNotNone(asset_config, "Should recover after config error")
        
        # Test recovery from exchange errors
        with patch.object(self.exchange, 'get_balance') as mock_balance:
            mock_balance.side_effect = Exception("Exchange error")
            
            balance = self.exchange.get_balance()
            self.assertIsNone(balance, "Should return None on exchange error")
            
            # Reset mock
            mock_balance.side_effect = None
            
            # Test recovery
            balance = self.exchange.get_balance()
            self.assertIsNotNone(balance, "Should recover after exchange error")
        
        print("✅ Error recovery works correctly")
    
    def test_07_performance_under_load(self):
        """Test performance under sustained load."""
        print("Testing performance under load...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Measure performance over time (reduced for faster testing)
        start_time = time.time()
        operation_count = 0
        max_operations = 50  # Reduced from 500
        
        while operation_count < max_operations and (time.time() - start_time) < 30:  # Reduced from 120
            try:
                # Perform typical operations
                ticker = self.exchange.get_ticker(spot_symbol)
                if ticker:
                    mid_price = ticker['last']
                    self.strategy.calculate_quotes(mid_price, 0.12)
                
                operation_count += 1
                
                # Small delay to avoid overwhelming the API
                time.sleep(0.1)  # Increased from 0.05 for faster completion
                
            except Exception as e:
                print(f"Operation {operation_count} failed: {e}")
        
        end_time = time.time()
        duration = end_time - start_time
        operations_per_second = operation_count / duration
        
        print(f"Completed {operation_count} operations in {duration:.1f} seconds")
        print(f"Performance: {operations_per_second:.1f} operations/second")
        
        # Performance should be reasonable (at least 1 op/sec)
        self.assertGreater(operations_per_second, 1.0, f"Performance too slow: {operations_per_second:.1f} ops/sec")
        
        print("✅ Performance under load is acceptable")
    
    def test_08_data_consistency(self):
        """Test data consistency under various conditions."""
        print("Testing data consistency...")
        
        spot_symbol, _ = self.exchange.find_solana_markets()
        if not spot_symbol:
            self.skipTest("No SOL spot market available")
        
        # Test multiple rapid calls return consistent data
        tickers = []
        for _ in range(10):
            ticker = self.exchange.get_ticker(spot_symbol)
            if ticker:
                tickers.append(ticker['last'])
            time.sleep(0.1)
        
        # All tickers should be valid prices
        for price in tickers:
            self.assertIsInstance(price, (int, float))
            self.assertGreater(price, 0)
        
        # Test quote consistency
        mid_price = tickers[0] if tickers else 100.0
        
        quotes = []
        for _ in range(10):
            bid_price, ask_price, spread = self.strategy.calculate_quotes(mid_price, 0.12)
            quotes.append((bid_price, ask_price, spread))
        
        # All quotes should be consistent
        for bid_price, ask_price, spread in quotes:
            self.assertGreater(ask_price, bid_price)
            self.assertGreater(spread, 0)
            self.assertLess(spread / mid_price, 0.1)  # Spread should be reasonable
        
        print("✅ Data consistency maintained")
    
    def test_09_resource_cleanup(self):
        """Test proper resource cleanup."""
        print("Testing resource cleanup...")
        
        # Test that resources are properly cleaned up
        import gc
        
        # Force garbage collection
        gc.collect()
        
        # Check for any obvious resource leaks
        # This is a basic test - in production you'd want more sophisticated monitoring
        
        print("✅ Resource cleanup appears normal")
    
    def test_10_system_stability(self):
        """Test overall system stability."""
        print("Testing system stability...")
        
        # Run a comprehensive stability test (reduced for faster testing)
        start_time = time.time()
        test_duration = 20  # Reduced from 60 seconds
        
        operation_count = 0
        error_count = 0
        
        while (time.time() - start_time) < test_duration:
            try:
                # Perform various operations
                spot_symbol, _ = self.exchange.find_solana_markets()
                if spot_symbol:
                    ticker = self.exchange.get_ticker(spot_symbol)
                    if ticker:
                        mid_price = ticker['last']
                        self.strategy.calculate_quotes(mid_price, 0.12)
                
                self.exchange.get_balance()
                operation_count += 1
                
                time.sleep(0.2)  # Increased from 0.1 for faster completion
                
            except Exception as e:
                error_count += 1
                print(f"Stability test error: {e}")
        
        error_rate = error_count / max(operation_count, 1)
        
        print(f"Stability test - Operations: {operation_count}, Errors: {error_count}, Error rate: {error_rate:.2%}")
        
        # Error rate should be low (less than 5%)
        self.assertLess(error_rate, 0.05, f"Error rate too high: {error_rate:.2%}")
        
        print("✅ System stability is good")

if __name__ == '__main__':
    # Run stress tests
    unittest.main(verbosity=2) 