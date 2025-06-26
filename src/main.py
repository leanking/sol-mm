import time
import signal
import sys
import os
from typing import Dict, Any, Optional
from config import ConfigManager
from logger import MarketMakerLogger
from exchange import HyperliquidExchange
from strategy import MarketMakingStrategy
from volatility import VolatilityCalculator
from risk_manager import RiskManager

class MarketMaker:
    """Main market making program orchestrator."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the market maker.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.running = False
        self.components = {}
        
        # Performance tracking
        self.cycle_times = []
        self.last_cycle_time = 0.0
        self.performance_stats = {}
        
        # Initialize components
        self._initialize_components()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _initialize_components(self) -> None:
        """Initialize all program components."""
        try:
            # Initialize configuration
            self.components['config'] = ConfigManager(self.config_path)
            
            # Initialize logger with log level from environment variable
            log_level = os.getenv("LOG_LEVEL", "INFO")
            self.components['logger'] = MarketMakerLogger(log_level=log_level)
            
            # Initialize exchange
            self.components['exchange'] = HyperliquidExchange(
                self.components['config'],
                self.components['logger']
            )
            
            # Initialize volatility calculator
            self.components['volatility'] = VolatilityCalculator(
                self.components['config'],
                self.components['logger']
            )
            
            # Initialize risk manager
            self.components['risk'] = RiskManager(
                self.components['config'],
                self.components['logger']
            )
            
            # Initialize strategy
            self.components['strategy'] = MarketMakingStrategy(
                self.components['config'],
                self.components['exchange'],
                self.components['volatility'],
                self.components['risk'],
                self.components['logger']
            )
            
            self.components['logger'].info("All components initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize components: {e}")
            sys.exit(1)
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        self.components['logger'].info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
    
    def connect_to_exchange(self) -> bool:
        """Connect to the exchange.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            success = self.components['exchange'].connect()
            if success:
                self.components['logger'].info("Successfully connected to exchange")
            else:
                self.components['logger'].error("Failed to connect to exchange")
            return success
            
        except Exception as e:
            self.components['logger'].log_error(e, "Exchange connection")
            return False
    
    def validate_configuration(self) -> bool:
        """Validate configuration and market setup.
        
        Returns:
            True if validation successful, False otherwise
        """
        try:
            config = self.components['config']
            exchange = self.components['exchange']
            logger = self.components['logger']
            
            # Check required configuration
            asset_config = config.get_asset_config()
            if not asset_config.get('symbol'):
                logger.error("No trading symbol configured")
                return False
            
            # Discover and validate markets using fetchMarkets
            spot_symbol, perp_symbol = exchange.find_solana_markets()
            
            if not spot_symbol:
                logger.error("No SOL spot market found")
                return False
            
            if not perp_symbol:
                logger.error("No SOL perpetual market found")
                return False
            
            # Validate that markets exist and are accessible
            spot_market = exchange.get_market_info(spot_symbol)
            perp_market = exchange.get_market_info(perp_symbol)
            
            if not spot_market:
                logger.error(f"Spot market {spot_symbol} not accessible")
                return False
            
            if not perp_market:
                logger.error(f"Perpetual market {perp_symbol} not accessible")
                return False
            
            logger.info(f"Validated markets: {spot_symbol}, {perp_symbol}")
            return True
            
        except Exception as e:
            self.components['logger'].log_error(e, "Configuration validation")
            return False
    
    def run_single_cycle(self) -> bool:
        """Run a single market making cycle with performance monitoring and step profiling."""
        cycle_start_time = time.time()
        step_times = {}
        try:
            strategy = self.components['strategy']
            logger = self.components['logger']
            t0 = time.time()
            result = strategy.execute_strategy_cycle()
            step_times['execute_strategy_cycle'] = time.time() - t0
            cycle_time = time.time() - cycle_start_time
            self.last_cycle_time = cycle_time
            self.cycle_times.append(cycle_time)
            if len(self.cycle_times) > 100:
                self.cycle_times = self.cycle_times[-100:]
            if result['success']:
                logger.info(f"Cycle completed: Mid={result['mid_price']:.4f}, "
                          f"Spread={result['spread']:.4f}, Vol={result['volatility']:.4f}, "
                          f"Time={cycle_time:.3f}s, StepTimes={step_times}")
                logger.log_inventory(
                    result['spot_inventory'],
                    result['funding_income']
                )
                if cycle_time > 5.0:
                    logger.warning(f"Cycle time exceeded 5s: {cycle_time:.3f}s")
                return True
            else:
                if result.get('trading_paused'):
                    logger.warning(f"Trading paused: {result['error']}")
                else:
                    logger.error(f"Cycle failed: {result['error']}")
                return False
        except Exception as e:
            cycle_time = time.time() - cycle_start_time
            self.last_cycle_time = cycle_time
            self.cycle_times.append(cycle_time)
            self.components['logger'].log_error(e, "Strategy cycle")
            return False
    
    def optimize_update_interval(self, current_interval: float) -> float:
        """Optimize update interval based on performance.
        
        Args:
            current_interval: Current update interval
            
        Returns:
            Optimized update interval
        """
        if not self.cycle_times:
            return current_interval
        
        avg_cycle_time = sum(self.cycle_times) / len(self.cycle_times)
        
        # If cycles are taking longer than 80% of the interval, increase it
        if avg_cycle_time > current_interval * 0.8:
            new_interval = max(current_interval * 1.2, avg_cycle_time * 1.1)
            self.components['logger'].info(f"Optimizing interval: {current_interval}s -> {new_interval:.1f}s "
                                         f"(avg cycle time: {avg_cycle_time:.2f}s)")
            return new_interval
        
        # If cycles are much faster, we can decrease the interval
        elif avg_cycle_time < current_interval * 0.3:
            new_interval = max(current_interval * 0.8, 1.0)  # Minimum 1 second
            self.components['logger'].info(f"Optimizing interval: {current_interval}s -> {new_interval:.1f}s "
                                         f"(avg cycle time: {avg_cycle_time:.2f}s)")
            return new_interval
        
        return current_interval
    
    def should_skip_cycle(self, current_volatility: float) -> bool:
        """Determine if a cycle should be skipped for performance reasons.
        
        Args:
            current_volatility: Current market volatility
            
        Returns:
            True if cycle should be skipped
        """
        # Skip if last cycle took too long
        if self.last_cycle_time > 2.0:  # More than 2 seconds
            self.components['logger'].warning(f"Skipping cycle due to slow execution: {self.last_cycle_time:.2f}s")
            return True
        # Always trade: never skip due to low volatility
        return False
    
    def collect_performance_stats(self) -> Dict[str, Any]:
        """Collect performance statistics from all components.
        
        Returns:
            Dictionary with performance statistics
        """
        stats = {
            'cycle_times': {
                'avg': sum(self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0,
                'min': min(self.cycle_times) if self.cycle_times else 0,
                'max': max(self.cycle_times) if self.cycle_times else 0,
                'count': len(self.cycle_times)
            },
            'exchange': self.components['exchange'].get_performance_stats(),
            'volatility': self.components['volatility'].get_cache_stats()
        }
        
        return stats
    
    def log_performance_summary(self) -> None:
        """Log performance summary."""
        stats = self.collect_performance_stats()
        logger = self.components['logger']
        
        logger.info("=== PERFORMANCE SUMMARY ===")
        logger.info(f"Cycle times - Avg: {stats['cycle_times']['avg']:.3f}s, "
                   f"Min: {stats['cycle_times']['min']:.3f}s, "
                   f"Max: {stats['cycle_times']['max']:.3f}s")
        
        # Exchange performance
        exchange_stats = stats['exchange']
        if 'operation_averages' in exchange_stats:
            logger.info("Exchange operations:")
            for op, op_stats in exchange_stats['operation_averages'].items():
                logger.info(f"  {op}: {op_stats['mean']:.3f}s avg")
        
        # Volatility cache performance
        vol_stats = stats['volatility']
        logger.info(f"Volatility cache - Hit rate: {vol_stats['hit_rate']:.1f}%, "
                   f"Avg calc time: {vol_stats['avg_calculation_time']:.3f}s")
        
        # Performance recommendations
        optimizer = self.components['exchange'].performance_optimizer
        recommendations = optimizer.get_recommendations()
        if recommendations:
            logger.info("Performance recommendations:")
            for rec in recommendations:
                logger.info(f"  - {rec}")
    
    def run(self) -> None:
        """Run the main market making loop with performance optimization."""
        try:
            logger = self.components['logger']
            config = self.components['config']
            
            logger.info("Starting market making program...")
            
            # Connect to exchange
            if not self.connect_to_exchange():
                logger.error("Failed to connect to exchange, exiting")
                return
            
            # Validate configuration
            if not self.validate_configuration():
                logger.error("Configuration validation failed, exiting")
                return
            
            # Get update interval
            update_interval = config.get_trading_config().get('update_interval', 5)
            
            logger.info(f"Starting market making loop with {update_interval}s intervals")
            
            self.running = True
            cycle_count = 0
            last_performance_log = time.time()
            
            while self.running:
                try:
                    cycle_count += 1
                    logger.debug(f"=== Cycle {cycle_count} START ===")
                    logger.debug(f"Sleeping for {update_interval}s before next cycle...")
                    # Calculate real volatility before skip check
                    strategy = self.components['strategy']
                    volatility = self.components['volatility'].calculate_volatility(
                        strategy.spot_symbol,
                        strategy.volatility_config.get('atr_period', 14),
                        strategy.volatility_config.get('timeframe', '1h')
                    )
                    logger.debug(f"Cycle {cycle_count}: Measured volatility: {volatility}")
                    if self.should_skip_cycle(volatility):
                        logger.debug(f"Cycle {cycle_count} skipped (should_skip_cycle returned True)")
                        time.sleep(update_interval)
                        continue
                    logger.debug(f"Cycle {cycle_count}: Running strategy cycle...")
                    # Run strategy cycle
                    success = self.run_single_cycle()
                    logger.debug(f"Cycle {cycle_count}: Strategy cycle completed. Success: {success}")
                    if not success:
                        logger.warning(f"Cycle {cycle_count} failed. Waiting {update_interval * 2}s before retrying.")
                        time.sleep(update_interval * 2)
                    else:
                        # Optimize interval based on performance
                        update_interval = self.optimize_update_interval(update_interval)
                        logger.debug(f"Cycle {cycle_count}: Sleeping for {update_interval}s after successful cycle.")
                        time.sleep(update_interval)
                    # Periodic cleanup and performance logging
                    if cycle_count % 10 == 0:
                        logger.debug(f"Cycle {cycle_count}: Clearing caches.")
                        self.components['volatility'].clear_cache()
                        self.components['exchange'].clear_performance_cache()
                        logger.debug("Cleared caches")
                    # Log performance summary every 5 minutes
                    if time.time() - last_performance_log > 300:  # 5 minutes
                        logger.debug(f"Cycle {cycle_count}: Logging performance summary.")
                        self.log_performance_summary()
                        last_performance_log = time.time()
                    logger.debug(f"=== Cycle {cycle_count} END ===")
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt")
                    break
                except Exception as e:
                    logger.log_error(e, f"Main loop cycle {cycle_count}")
                    logger.error(f"Exception in main loop cycle {cycle_count}: {e}")
                    time.sleep(update_interval)
            logger.info("Market making loop stopped")
        except Exception as e:
            self.components['logger'].log_error(e, "Main program execution")
        finally:
            self.cleanup()
    
    def stop(self) -> None:
        """Stop the market making program."""
        self.components['logger'].info("Stopping market making program...")
        self.running = False
    
    def cleanup(self) -> None:
        """Clean up resources before shutdown."""
        try:
            logger = self.components['logger']
            strategy = self.components['strategy']
            
            # Cancel all open orders
            strategy.cancel_spot_orders()
            
            # Log final summary
            strategy_summary = strategy.get_strategy_summary()
            risk_summary = self.components['risk'].get_risk_summary()
            
            logger.info("=== FINAL SUMMARY ===")
            logger.info(f"Strategy: {strategy_summary}")
            logger.info(f"Risk: {str(risk_summary)}")
            
            # Log final performance summary
            self.log_performance_summary()
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def get_status(self) -> dict:
        """Get current program status.
        
        Returns:
            Dictionary with current status
        """
        try:
            return {
                'running': self.running,
                'strategy': self.components['strategy'].get_strategy_summary(),
                'risk': self.components['risk'].get_risk_summary(),
                'exchange_connected': self.components['exchange'].connected,
                'performance': self.collect_performance_stats()
            }
        except Exception as e:
            return {'error': str(e)}


def main():
    """Main entry point for the market making program."""
    try:
        # Create and run market maker
        market_maker = MarketMaker()
        market_maker.run()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 