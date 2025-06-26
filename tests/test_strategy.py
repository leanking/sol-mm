import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategy import MarketMakingStrategy
from config import ConfigManager
from logger import MarketMakerLogger

class TestMarketMakingStrategy(unittest.TestCase):
    """Test cases for MarketMakingStrategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get_asset_config.return_value = {
            'symbol': 'SOL/USDC',
            'price': 143.0,
            'inventory_size': 10.0,
            'base_spread': 0.00245,
            'leverage': 10.0
        }
        self.mock_config.get_fees_config.return_value = {
            'spot_maker': 0.000384,
            'perp_maker': 0.000144
        }
        self.mock_config.get_volatility_config.return_value = {
            'atr_period': 14,
            'timeframe': '1h',
            'spread_scale_factor': 0.5
        }
        self.mock_config.get.return_value = 0.08 / 365  # Default funding rate
        
        # Mock other components
        self.mock_exchange = Mock()
        self.mock_volatility = Mock()
        self.mock_risk = Mock()
        self.mock_logger = Mock(spec=MarketMakerLogger)
        
        # Mock exchange methods
        self.mock_exchange.get_symbol_for_perp.return_value = 'SOL/USDC:USDC'
        
        # Create strategy instance
        self.strategy = MarketMakingStrategy(
            self.mock_config,
            self.mock_exchange,
            self.mock_volatility,
            self.mock_risk,
            self.mock_logger
        )
    
    def test_initialization(self):
        """Test strategy initialization."""
        self.assertEqual(self.strategy.spot_symbol, 'SOL/USDC')
        self.assertEqual(self.strategy.perp_symbol, 'SOL/USDC:USDC')
        self.assertEqual(self.strategy.base_spread, 0.00245)
        self.assertEqual(self.strategy.inventory_size, 10.0)
        self.assertEqual(self.strategy.leverage, 10.0)
    
    def test_calculate_quotes(self):
        """Test quote calculation."""
        mid_price = 143.0
        volatility = 0.12
        
        # Mock volatility calculator
        self.mock_volatility.adjust_spread.return_value = 0.0026
        
        bid_price, ask_price, spread = self.strategy.calculate_quotes(mid_price, volatility)
        
        # Verify calculations
        expected_spread = 0.0026
        expected_bid = mid_price * (1 - expected_spread / 2)
        expected_ask = mid_price * (1 + expected_spread / 2)
        
        self.assertAlmostEqual(bid_price, expected_bid, places=4)
        self.assertAlmostEqual(ask_price, expected_ask, places=4)
        self.assertAlmostEqual(spread, expected_spread, places=4)
    
    def test_calculate_hedge_size(self):
        """Test hedge size calculation."""
        spot_inventory = 5.0
        hedge_size = self.strategy.calculate_hedge_size(spot_inventory)
        
        # Should be negative (short) and scaled by leverage
        expected_hedge = -spot_inventory * self.strategy.leverage
        self.assertEqual(hedge_size, expected_hedge)
    
    def test_calculate_funding_income(self):
        """Test funding income calculation."""
        perp_position = -50.0  # Short position
        funding_rate = 0.0002  # 0.02% per period
        
        # Mock ticker
        self.mock_exchange.get_ticker.return_value = {'last': 143.0}
        
        funding_income = self.strategy.calculate_funding_income(perp_position, funding_rate)
        
        # Expected: abs(-50) * 143 * 0.0002 = 1.43
        expected_income = abs(perp_position) * 143.0 * funding_rate
        self.assertAlmostEqual(funding_income, expected_income, places=2)
    
    def test_get_current_inventory(self):
        """Test inventory retrieval."""
        # Mock balance
        mock_balance = {
            'SOL': {'free': 5.5, 'used': 0.0, 'total': 5.5}
        }
        self.mock_exchange.get_balance.return_value = mock_balance
        
        inventory = self.strategy.get_current_inventory()
        
        self.assertEqual(inventory, 5.5)
        self.assertEqual(self.strategy.current_inventory, 5.5)
    
    def test_get_current_perp_position(self):
        """Test perpetual position retrieval."""
        # Mock positions
        mock_positions = [
            {'symbol': 'SOL/USDC:USDC', 'size': -50.0, 'notional': 7150.0}
        ]
        self.mock_exchange.get_positions.return_value = mock_positions
        
        position = self.strategy.get_current_perp_position()
        
        self.assertEqual(position, -50.0)

if __name__ == '__main__':
    unittest.main() 