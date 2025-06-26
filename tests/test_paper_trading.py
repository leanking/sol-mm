#!/usr/bin/env python3
"""
Paper trading test for the market maker system.
This simulates the complete market making process without placing real orders.
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta
from decimal import Decimal

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

class PaperTradingSimulator:
    """Simulates market making without placing real orders."""
    
    def __init__(self, duration_minutes=30, update_interval=30):
        """
        Initialize paper trading simulator.
        
        Args:
            duration_minutes: How long to run the simulation
            update_interval: Seconds between updates
        """
        self.duration_minutes = duration_minutes
        self.update_interval = update_interval
        
        # Initialize components
        self.config = ConfigManager()
        self.logger = MarketMakerLogger()
        self.exchange = HyperliquidExchange(self.config, self.logger)
        
        # Connect to exchange
        if not self.exchange.connect():
            raise Exception("Failed to connect to Hyperliquid")
        
        # Initialize strategy components
        self.volatility = VolatilityCalculator(self.config, self.logger)
        self.risk = RiskManager(self.config, self.logger)
        self.strategy = MarketMakingStrategy(
            self.config, self.exchange, self.volatility, self.risk, self.logger
        )
        
        # Paper trading state
        self.paper_balance = {'USDC': 10000.0, 'SOL': 0.0}  # Starting balance
        self.paper_positions = []
        self.paper_orders = []
        self.trade_history = []
        self.pnl_history = []
        
        # Performance tracking
        self.start_time = None
        self.total_pnl = 0.0
        self.total_trades = 0
        self.successful_trades = 0
        
    def simulate_market_making(self):
        """Run the paper trading simulation."""
        print(f"Starting paper trading simulation for {self.duration_minutes} minutes...")
        print(f"Update interval: {self.update_interval} seconds")
        print("=" * 60)
        
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        
        try:
            while datetime.now() < end_time:
                self._simulate_one_cycle()
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            print("\nSimulation interrupted by user")
        
        self._print_final_results()
    
    def _simulate_one_cycle(self):
        """Simulate one market making cycle."""
        current_time = datetime.now()
        
        # Get current market data
        spot_symbol, perp_symbol = self.exchange.find_solana_markets()
        if not spot_symbol:
            print("❌ No SOL spot market found")
            return
        
        # Get market data
        ticker = self.exchange.get_ticker(spot_symbol)
        if not ticker:
            print("❌ Failed to get ticker data")
            return
        
        mid_price = ticker['last']
        
        # Calculate volatility
        atr = self.volatility.calculate_atr(spot_symbol)
        if atr is None:
            atr = 0.12  # Default volatility
        
        # Calculate quotes
        bid_price, ask_price, spread = self.strategy.calculate_quotes(mid_price, atr)
        
        # Simulate order placement and execution
        self._simulate_order_execution(spot_symbol, bid_price, ask_price, mid_price)
        
        # Update PnL
        current_pnl = self._calculate_paper_pnl(mid_price)
        self.pnl_history.append({
            'timestamp': current_time,
            'mid_price': mid_price,
            'pnl': current_pnl,
            'balance_usdc': self.paper_balance['USDC'],
            'balance_sol': self.paper_balance['SOL']
        })
        
        # Print status
        self._print_status(current_time, mid_price, bid_price, ask_price, spread, current_pnl)
    
    def _simulate_order_execution(self, symbol, bid_price, ask_price, mid_price):
        """Simulate order execution based on market conditions."""
        # Simulate some orders getting filled based on market movement
        # This is a simplified simulation - in reality, fill rates depend on many factors
        
        # Calculate order sizes based on current balance
        max_order_size = min(self.paper_balance['USDC'] / ask_price * 0.1, 
                           self.paper_balance['SOL'] * 0.1)
        max_order_size = max(max_order_size, 0.01)  # Minimum size
        
        # Simulate bid order fill (buy SOL)
        if self.paper_balance['USDC'] >= bid_price * max_order_size:
            # 30% chance of bid getting filled
            if self._random_fill(0.3):
                order_size = max_order_size
                cost = bid_price * order_size
                
                self.paper_balance['USDC'] -= cost
                self.paper_balance['SOL'] += order_size
                
                self.trade_history.append({
                    'timestamp': datetime.now(),
                    'side': 'buy',
                    'symbol': symbol,
                    'size': order_size,
                    'price': bid_price,
                    'cost': cost
                })
                
                self.total_trades += 1
                self.successful_trades += 1
        
        # Simulate ask order fill (sell SOL)
        if self.paper_balance['SOL'] >= max_order_size:
            # 30% chance of ask getting filled
            if self._random_fill(0.3):
                order_size = max_order_size
                revenue = ask_price * order_size
                
                self.paper_balance['SOL'] -= order_size
                self.paper_balance['USDC'] += revenue
                
                self.trade_history.append({
                    'timestamp': datetime.now(),
                    'side': 'sell',
                    'symbol': symbol,
                    'size': order_size,
                    'price': ask_price,
                    'revenue': revenue
                })
                
                self.total_trades += 1
                self.successful_trades += 1
    
    def _random_fill(self, probability):
        """Simulate random order fill based on probability."""
        import random
        return random.random() < probability
    
    def _calculate_paper_pnl(self, current_price):
        """Calculate paper trading PnL."""
        # Calculate unrealized PnL from SOL holdings
        sol_value = self.paper_balance['SOL'] * current_price
        total_value = self.paper_balance['USDC'] + sol_value
        initial_value = 10000.0  # Starting USDC balance
        
        return total_value - initial_value
    
    def _print_status(self, timestamp, mid_price, bid_price, ask_price, spread, pnl):
        """Print current status."""
        spread_pct = (spread / mid_price) * 100
        
        print(f"[{timestamp.strftime('%H:%M:%S')}] "
              f"Price: ${mid_price:.2f} | "
              f"Bid: ${bid_price:.2f} | "
              f"Ask: ${ask_price:.2f} | "
              f"Spread: {spread_pct:.3f}% | "
              f"PnL: ${pnl:.2f} | "
              f"SOL: {self.paper_balance['SOL']:.4f} | "
              f"USDC: ${self.paper_balance['USDC']:.2f}")
    
    def _print_final_results(self):
        """Print final simulation results."""
        print("\n" + "=" * 60)
        print("PAPER TRADING SIMULATION RESULTS")
        print("=" * 60)
        
        # Calculate final metrics
        final_pnl = self.pnl_history[-1]['pnl'] if self.pnl_history else 0
        total_return = (final_pnl / 10000.0) * 100
        
        print(f"Duration: {self.duration_minutes} minutes")
        print(f"Total trades: {self.total_trades}")
        print(f"Successful trades: {self.successful_trades}")
        print(f"Success rate: {(self.successful_trades/self.total_trades*100):.1f}%" if self.total_trades > 0 else "N/A")
        print(f"Final PnL: ${final_pnl:.2f}")
        print(f"Total return: {total_return:.2f}%")
        print(f"Final balance - SOL: {self.paper_balance['SOL']:.4f}, USDC: ${self.paper_balance['USDC']:.2f}")
        
        # Save results to file
        self._save_results()
    
    def _save_results(self):
        """Save simulation results to file."""
        results = {
            'simulation_date': datetime.now().isoformat(),
            'duration_minutes': self.duration_minutes,
            'update_interval': self.update_interval,
            'final_pnl': self.pnl_history[-1]['pnl'] if self.pnl_history else 0,
            'total_trades': self.total_trades,
            'successful_trades': self.successful_trades,
            'final_balance': self.paper_balance,
            'trade_history': [
                {
                    'timestamp': trade['timestamp'].isoformat(),
                    'side': trade['side'],
                    'symbol': trade['symbol'],
                    'size': trade['size'],
                    'price': trade['price']
                }
                for trade in self.trade_history
            ],
            'pnl_history': [
                {
                    'timestamp': pnl['timestamp'].isoformat(),
                    'mid_price': pnl['mid_price'],
                    'pnl': pnl['pnl']
                }
                for pnl in self.pnl_history
            ]
        }
        
        filename = f"paper_trading_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {filename}")

def main():
    """Run paper trading simulation."""
    print("Hyperliquid Market Maker - Paper Trading Simulation")
    print("=" * 60)
    
    # Configuration
    duration = 30  # minutes
    update_interval = 30  # seconds
    
    try:
        # Create and run simulator
        simulator = PaperTradingSimulator(duration, update_interval)
        simulator.simulate_market_making()
        
    except Exception as e:
        print(f"❌ Error during paper trading simulation: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main() 