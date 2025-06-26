#!/usr/bin/env python3
"""
Test script for enhanced market making strategy.
Validates configuration and strategy parameters for volume generation.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config import ConfigManager
from logger import MarketMakerLogger
from strategy import MarketMakingStrategy
from volatility import VolatilityCalculator
from risk_manager import RiskManager
from exchange import HyperliquidExchange

def test_configuration():
    """Test configuration loading and validation."""
    print("=== Testing Configuration ===")
    
    try:
        config = ConfigManager()
        
        # Test asset config
        asset_config = config.get_asset_config()
        print(f"Asset config: {asset_config}")
        
        # Test volume config
        volume_config = config.get_volume_config()
        print(f"Volume config: {volume_config}")
        
        # Test risk config
        risk_config = config.get_risk_config()
        print(f"Risk config: {risk_config}")
        
        # Test trading config
        trading_config = config.get_trading_config()
        print(f"Trading config: {trading_config}")
        
        # Validate key parameters
        assert asset_config['inventory_size'] >= 20.0, "Inventory size should be >= 20.0"
        assert asset_config['base_spread'] <= 0.002, "Base spread should be <= 0.2%"
        assert risk_config['max_inventory'] >= 25.0, "Max inventory should be >= 25.0"
        assert trading_config['trades_per_day'] >= 500, "Daily trades should be >= 500"
        assert volume_config['target_daily_volume'] >= 1000.0, "Target volume should be >= 1000.0"
        
        print("✅ Configuration validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def test_strategy_initialization():
    """Test strategy initialization with enhanced parameters."""
    print("\n=== Testing Strategy Initialization ===")
    
    try:
        # Initialize components
        config = ConfigManager()
        logger = MarketMakerLogger(log_level="INFO")
        
        # Mock exchange for testing
        class MockExchange:
            def __init__(self):
                self.connected = True
                self.markets = {
                    'USOL/USDC': {'type': 'spot'},
                    'SOL/USDC:USDC': {'type': 'swap'}
                }
            
            def find_solana_markets(self):
                return 'USOL/USDC', 'SOL/USDC:USDC'
            
            def get_symbol_for_perp(self, symbol):
                return 'SOL/USDC:USDC'
            
            def get_ticker(self, symbol):
                return {'last': 143.0}
            
            def get_balance(self):
                return {'USOL': {'free': 0.0}}
            
            def get_positions(self):
                return []
            
            def place_order(self, symbol, side, amount, price, order_type, market_type):
                return f"mock_order_{side}_{amount}"
            
            def cancel_order(self, order_id, symbol, market_type):
                return True
        
        exchange = MockExchange()
        volatility_calc = VolatilityCalculator(config, logger)
        risk_manager = RiskManager(config, logger)
        
        # Initialize strategy
        strategy = MarketMakingStrategy(config, exchange, volatility_calc, risk_manager, logger)
        
        # Test strategy parameters
        print(f"Strategy initialized with:")
        print(f"  - Spot symbol: {strategy.spot_symbol}")
        print(f"  - Perp symbol: {strategy.perp_symbol}")
        print(f"  - Base spread: {strategy.base_spread}")
        print(f"  - Inventory size: {strategy.inventory_size}")
        print(f"  - Order tiers: {strategy.order_tiers}")
        print(f"  - Target volume: {strategy.target_daily_volume}")
        print(f"  - Min spread: {strategy.min_spread}")
        print(f"  - Max spread: {strategy.max_spread}")
        print(f"  - Spread aggression: {strategy.spread_aggression}")
        
        # Validate strategy parameters
        assert strategy.order_tiers == 3, "Should have 3 order tiers"
        assert strategy.target_daily_volume >= 1000.0, "Target volume should be >= 1000.0"
        assert strategy.min_spread <= 0.001, "Min spread should be <= 0.1%"
        assert strategy.max_spread >= 0.005, "Max spread should be >= 0.5%"
        assert strategy.spread_aggression >= 0.8, "Spread aggression should be >= 0.8"
        
        print("✅ Strategy initialization passed")
        return True
        
    except Exception as e:
        print(f"❌ Strategy initialization failed: {e}")
        return False

def test_quote_calculation():
    """Test enhanced quote calculation with multiple tiers."""
    print("\n=== Testing Quote Calculation ===")
    
    try:
        # Initialize components
        config = ConfigManager()
        logger = MarketMakerLogger(log_level="INFO")
        
        # Mock exchange
        class MockExchange:
            def __init__(self):
                self.connected = True
                self.markets = {
                    'USOL/USDC': {'type': 'spot'},
                    'SOL/USDC:USDC': {'type': 'swap'}
                }
            
            def find_solana_markets(self):
                return 'USOL/USDC', 'SOL/USDC:USDC'
            
            def get_symbol_for_perp(self, symbol):
                return 'SOL/USDC:USDC'
            
            def get_ticker(self, symbol):
                return {'last': 143.0}
            
            def get_balance(self):
                return {'USOL': {'free': 0.0}}
            
            def get_positions(self):
                return []
        
        exchange = MockExchange()
        volatility_calc = VolatilityCalculator(config, logger)
        risk_manager = RiskManager(config, logger)
        strategy = MarketMakingStrategy(config, exchange, volatility_calc, risk_manager, logger)
        
        # Test quote calculation
        mid_price = 143.0
        volatility = 0.01  # 1% volatility
        
        quotes = strategy.calculate_quotes(mid_price, volatility)
        
        print(f"Generated {len(quotes)} quote tiers:")
        for i, (bid, ask, size) in enumerate(quotes):
            spread = (ask - bid) / mid_price
            print(f"  Tier {i+1}: Bid={bid:.4f}, Ask={ask:.4f}, Size={size:.2f}, Spread={spread:.4%}")
        
        # Validate quotes
        assert len(quotes) == 3, "Should generate 3 tiers"
        assert quotes[0][1] > quotes[0][0], "Ask should be higher than bid"
        assert quotes[1][1] > quotes[1][0], "Ask should be higher than bid"
        assert quotes[2][1] > quotes[2][0], "Ask should be higher than bid"
        
        # Check tier progression
        spread1 = (quotes[0][1] - quotes[0][0]) / mid_price
        spread2 = (quotes[1][1] - quotes[1][0]) / mid_price
        spread3 = (quotes[2][1] - quotes[2][0]) / mid_price
        
        assert spread2 > spread1, "Tier 2 should have wider spread than tier 1"
        assert spread3 > spread2, "Tier 3 should have wider spread than tier 2"
        
        print("✅ Quote calculation passed")
        return True
        
    except Exception as e:
        print(f"❌ Quote calculation failed: {e}")
        return False

def test_volume_tracking():
    """Test volume tracking functionality."""
    print("\n=== Testing Volume Tracking ===")
    
    try:
        # Initialize components
        config = ConfigManager()
        logger = MarketMakerLogger(log_level="INFO")
        
        # Mock exchange
        class MockExchange:
            def __init__(self):
                self.connected = True
                self.markets = {
                    'USOL/USDC': {'type': 'spot'},
                    'SOL/USDC:USDC': {'type': 'swap'}
                }
            
            def find_solana_markets(self):
                return 'USOL/USDC', 'SOL/USDC:USDC'
            
            def get_symbol_for_perp(self, symbol):
                return 'SOL/USDC:USDC'
            
            def get_ticker(self, symbol):
                return {'last': 143.0}
            
            def get_balance(self):
                return {'USOL': {'free': 0.0}}
            
            def get_positions(self):
                return []
        
        exchange = MockExchange()
        volatility_calc = VolatilityCalculator(config, logger)
        risk_manager = RiskManager(config, logger)
        strategy = MarketMakingStrategy(config, exchange, volatility_calc, risk_manager, logger)
        
        # Test volume tracking
        print(f"Initial daily volume: {strategy.daily_volume}")
        print(f"Target daily volume: {strategy.target_daily_volume}")
        
        # Simulate trade
        strategy.update_volume_metrics(trade_size=5.0)
        print(f"After 5 SOL trade: {strategy.daily_volume}")
        
        # Simulate more trades
        strategy.update_volume_metrics(trade_size=10.0)
        strategy.update_volume_metrics(trade_size=15.0)
        print(f"After additional trades: {strategy.daily_volume}")
        
        # Calculate progress
        progress = strategy.daily_volume / strategy.target_daily_volume
        print(f"Volume progress: {progress:.1%}")
        
        # Validate volume tracking
        assert strategy.daily_volume == 30.0, "Volume should be 30.0"
        assert progress == 0.03, "Progress should be 3%"
        
        print("✅ Volume tracking passed")
        return True
        
    except Exception as e:
        print(f"❌ Volume tracking failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Enhanced Market Making Strategy Test Suite")
    print("=" * 50)
    
    tests = [
        test_configuration,
        test_strategy_initialization,
        test_quote_calculation,
        test_volume_tracking
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced strategy is ready for deployment.")
        return True
    else:
        print("⚠️  Some tests failed. Please review configuration and implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 