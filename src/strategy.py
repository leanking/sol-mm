import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from config import ConfigManager
from exchange import HyperliquidExchange
from volatility import VolatilityCalculator
from risk_manager import RiskManager
from logger import MarketMakerLogger

class MarketMakingStrategy:
    """Implements the long spot, short perps market making strategy with enhanced volume generation."""
    
    def __init__(self, config: ConfigManager, exchange: HyperliquidExchange, 
                 volatility_calc: VolatilityCalculator, risk_manager: RiskManager,
                 logger: MarketMakerLogger):
        """Initialize market making strategy.
        
        Args:
            config: Configuration manager
            exchange: Exchange interface
            volatility_calc: Volatility calculator
            risk_manager: Risk manager
            logger: Logger instance
        """
        self.config = config
        self.exchange = exchange
        self.volatility_calc = volatility_calc
        self.risk_manager = risk_manager
        self.logger = logger
        
        # Set exchange in volatility calculator
        self.volatility_calc.set_exchange(exchange.exchange)
        
        # Load configuration
        self.asset_config = config.get_asset_config()
        self.fees_config = config.get_fees_config()
        self.volatility_config = config.get_volatility_config()
        self.volume_config = config.get_volume_config()
        
        # Strategy state - will be set after market discovery
        self.spot_symbol = None
        self.perp_symbol = None
        self.base_spread = self.asset_config['base_spread']
        self.inventory_size = self.asset_config['inventory_size']
        self.leverage = self.asset_config['leverage']
        
        # Enhanced volume generation parameters
        self.min_spread = self.volume_config.get('min_spread', 0.0005)  # 0.05% minimum spread for aggressive trading
        self.max_spread = self.volume_config.get('max_spread', 0.0050)  # 0.5% maximum spread
        self.spread_aggression = self.volume_config.get('spread_aggression', 0.8)  # How aggressive to be with spreads (0-1)
        self.order_tiers = self.volume_config.get('order_tiers', 3)  # Number of order tiers for better fill rates
        self.tier_spacing = self.volume_config.get('tier_spacing', 0.0002)  # Spread between tiers (0.02%)
        self.min_order_size = self.volume_config.get('min_order_size', 0.5)  # Minimum order size in SOL
        self.max_order_size = self.volume_config.get('max_order_size', 5.0)  # Maximum order size in SOL
        
        # Volume tracking
        self.daily_volume = 0.0
        self.last_volume_reset = None
        self.target_daily_volume = self.volume_config.get('target_daily_volume', 1000.0)  # Target daily volume in SOL
        self.volume_boost_factor = 1.0  # Dynamic volume boost based on performance
        
        # Current state
        self.current_inventory = 0.0
        self.current_spot_orders = []
        self.current_perp_orders = []
        self.last_mid_price = 0.0
        self.last_trade_time = 0.0
        self.consecutive_no_fills = 0
        
        # Discover markets
        self._discover_markets()
        
        self.logger.info(f"Initialized enhanced strategy for {self.spot_symbol} (perp: {self.perp_symbol})")
    
    def _discover_markets(self) -> None:
        """Discover SOL spot and perpetual markets using fetchMarkets."""
        try:
            # Try to find SOL markets using the new discovery method
            spot_symbol, perp_symbol = self.exchange.find_solana_markets()
            
            if spot_symbol and perp_symbol:
                self.spot_symbol = spot_symbol
                self.perp_symbol = perp_symbol
                self.logger.info(f"Discovered markets: {spot_symbol} and {perp_symbol}")
            else:
                # Fallback to config-based symbols
                self.spot_symbol = self.asset_config['symbol']
                self.perp_symbol = self.exchange.get_symbol_for_perp(self.spot_symbol)
                self.logger.warning(f"Using fallback symbols: {self.spot_symbol} and {self.perp_symbol}")
                
        except Exception as e:
            self.logger.log_error(e, "Market discovery")
            # Fallback to config-based symbols
            self.spot_symbol = self.asset_config['symbol']
            self.perp_symbol = self.exchange.get_symbol_for_perp(self.spot_symbol)
    
    def reset_daily_volume(self) -> None:
        """Reset daily volume tracking."""
        from datetime import datetime
        current_date = datetime.now().date()
        if self.last_volume_reset != current_date:
            self.daily_volume = 0.0
            self.last_volume_reset = current_date
            self.logger.info(f"Reset daily volume tracking. Target: {self.target_daily_volume} SOL")
    
    def calculate_aggressive_spread(self, mid_price: float, volatility: float) -> float:
        """Calculate aggressive spread for higher fill rates.
        
        Args:
            mid_price: Current mid price
            volatility: Current volatility measure
            
        Returns:
            Aggressive spread as decimal
        """
        try:
            # Calculate ATR for spread adjustment
            atr = self.volatility_calc.calculate_atr(
                self.spot_symbol,
                self.volatility_config.get('atr_period', 14),
                self.volatility_config.get('timeframe', '1h')
            )
            
            # Base spread with volatility adjustment
            base_spread = self.base_spread
            
            # Adjust based on volatility (reduce spread in low volatility)
            if volatility < 0.01:  # Low volatility
                base_spread *= 0.7  # Reduce spread by 30%
            elif volatility > 0.02:  # High volatility
                base_spread *= 1.2  # Increase spread by 20%
            
            # Apply aggression factor
            aggressive_spread = base_spread * (1 - self.spread_aggression * 0.5)
            
            # Ensure spread is within bounds
            aggressive_spread = max(self.min_spread, min(aggressive_spread, self.max_spread))
            
            # Adjust based on fill rate
            if self.consecutive_no_fills > 5:
                aggressive_spread *= 0.8  # Reduce spread if not getting fills
                self.consecutive_no_fills = 0
            
            # Adjust based on volume targets
            volume_progress = self.daily_volume / self.target_daily_volume
            if volume_progress < 0.3:  # Behind on volume
                aggressive_spread *= 0.9  # More aggressive
            elif volume_progress > 0.8:  # Ahead on volume
                aggressive_spread *= 1.1  # Less aggressive
            
            self.logger.debug(f"Aggressive spread: {aggressive_spread:.6f} (base: {base_spread:.6f}, vol: {volatility:.4f})")
            
            return aggressive_spread
            
        except Exception as e:
            self.logger.log_error(e, "Aggressive spread calculation")
            return self.base_spread
    
    def calculate_order_sizes(self, base_size: float) -> List[float]:
        """Calculate order sizes for multiple tiers.
        
        Args:
            base_size: Base order size
            
        Returns:
            List of order sizes for each tier
        """
        sizes = []
        for i in range(self.order_tiers):
            # Tier 1: 40% of base size (closest to mid)
            # Tier 2: 35% of base size
            # Tier 3: 25% of base size (furthest from mid)
            tier_factor = [0.4, 0.35, 0.25][i]
            size = base_size * tier_factor
            
            # Ensure minimum and maximum sizes
            size = max(self.min_order_size, min(size, self.max_order_size))
            sizes.append(size)
        
        return sizes
    
    def calculate_quotes(self, mid_price: float, volatility: float) -> List[Tuple[float, float, float]]:
        """Calculate multiple tiers of bid and ask prices for better fill rates.
        
        Args:
            mid_price: Current mid price
            volatility: Current volatility measure
            
        Returns:
            List of (bid_price, ask_price, order_size) tuples for each tier
        """
        try:
            # Calculate aggressive spread
            spread = self.calculate_aggressive_spread(mid_price, volatility)
            
            # Calculate base order size
            base_order_size = self.inventory_size / (2 * self.order_tiers)
            
            # Calculate order sizes for each tier
            order_sizes = self.calculate_order_sizes(base_order_size)
            
            quotes = []
            for i, order_size in enumerate(order_sizes):
                # Calculate tier-specific spread
                tier_spread = spread + (i * self.tier_spacing)
                
                # Calculate bid and ask prices for this tier
                spread_half = tier_spread / 2
                bid_price = mid_price * (1 - spread_half)
                ask_price = mid_price * (1 + spread_half)
                
                quotes.append((bid_price, ask_price, order_size))
                
                self.logger.debug(f"Tier {i+1}: Bid={bid_price:.4f}, Ask={ask_price:.4f}, Size={order_size:.2f}")
            
            self.logger.log_quote(self.spot_symbol, quotes[0][0], quotes[0][1], spread)
            
            return quotes
            
        except Exception as e:
            self.logger.log_error(e, "Quote calculation")
            # Fallback to single tier
            spread_half = self.base_spread / 2
            bid_price = mid_price * (1 - spread_half)
            ask_price = mid_price * (1 + spread_half)
            return [(bid_price, ask_price, self.inventory_size / 2)]
    
    def get_current_inventory(self) -> float:
        """Get current spot inventory.
        
        Returns:
            Current inventory size (positive for long, negative for short)
        """
        try:
            balance = self.exchange.get_balance()
            if balance:
                # Extract base currency (e.g., SOL from SOL/USDC)
                base_currency = self.spot_symbol.split('/')[0]
                if base_currency in balance:
                    inventory = balance[base_currency]['free']
                    self.current_inventory = inventory
                    return inventory
            
            return self.current_inventory
            
        except Exception as e:
            self.logger.log_error(e, "Getting current inventory")
            return self.current_inventory
    
    def get_current_perp_position(self) -> float:
        """Get current perpetual position size.
        
        Returns:
            Current perp position size (negative for short)
        """
        try:
            positions = self.exchange.get_positions()
            if positions:
                for position in positions:
                    if position.get('symbol') == self.perp_symbol:
                        return position.get('size', 0.0)
            
            return 0.0
            
        except Exception as e:
            self.logger.log_error(e, "Getting current perp position")
            return 0.0
    
    def calculate_hedge_size(self, spot_inventory: float) -> float:
        """Calculate required hedge size for perpetual position.
        
        Args:
            spot_inventory: Current spot inventory
            
        Returns:
            Required hedge size (negative for short)
        """
        # Hedge spot inventory with short perps
        # If we have long spot, we need short perps
        hedge_size = -spot_inventory * self.leverage
        return hedge_size
    
    def place_spot_quotes(self, quotes: List[Tuple[float, float, float]]) -> List[str]:
        """Place multiple tiers of spot market making quotes.
        
        Args:
            quotes: List of (bid_price, ask_price, order_size) tuples
            
        Returns:
            List of order IDs
        """
        order_ids = []
        
        try:
            # Cancel existing spot orders
            self.cancel_spot_orders()
            
            # Place orders for each tier
            for i, (bid_price, ask_price, order_size) in enumerate(quotes):
                # Place bid order
                if order_size > 0:
                    bid_order_id = self.exchange.place_order(
                        self.spot_symbol, 'buy', order_size, bid_price, 'limit', 'spot'
                    )
                    if bid_order_id:
                        order_ids.append(bid_order_id)
                        self.current_spot_orders.append(bid_order_id)
                        self.logger.debug(f"Placed tier {i+1} bid: {order_size:.2f} @ {bid_price:.4f}")
                
                # Place ask order
                if order_size > 0:
                    ask_order_id = self.exchange.place_order(
                        self.spot_symbol, 'sell', order_size, ask_price, 'limit', 'spot'
                    )
                    if ask_order_id:
                        order_ids.append(ask_order_id)
                        self.current_spot_orders.append(ask_order_id)
                        self.logger.debug(f"Placed tier {i+1} ask: {order_size:.2f} @ {ask_price:.4f}")
            
            self.logger.info(f"Placed {len(order_ids)} spot orders across {len(quotes)} tiers")
            
        except Exception as e:
            self.logger.log_error(e, "Placing spot quotes")
        
        return order_ids
    
    def place_hedge_order(self, hedge_size: float, current_perp_size: float) -> Optional[str]:
        """Place hedge order to maintain delta-neutral position.
        
        Args:
            hedge_size: Required hedge size
            current_perp_size: Current perp position size
            
        Returns:
            Order ID if placed, None otherwise
        """
        try:
            # Calculate required adjustment
            adjustment = hedge_size - current_perp_size
            
            if abs(adjustment) < 0.01:  # Small adjustment threshold
                return None
            
            # Get current perp price
            perp_ticker = self.exchange.get_ticker(self.perp_symbol)
            if not perp_ticker:
                return None
            
            perp_price = perp_ticker['last']
            
            # Place hedge order
            side = 'sell' if adjustment < 0 else 'buy'
            order_id = self.exchange.place_order(
                self.perp_symbol, side, abs(adjustment), perp_price, 'market', 'swap'
            )
            
            if order_id:
                self.logger.info(f"Placed hedge order: {side} {abs(adjustment)} {self.perp_symbol}")
            
            return order_id
            
        except Exception as e:
            self.logger.log_error(e, "Placing hedge order")
            return None
    
    def cancel_spot_orders(self) -> None:
        """Cancel all current spot orders."""
        try:
            for order_id in self.current_spot_orders:
                self.exchange.cancel_order(order_id, self.spot_symbol, 'spot')
            
            self.current_spot_orders.clear()
            self.logger.info("Cancelled all spot orders")
            
        except Exception as e:
            self.logger.log_error(e, "Cancelling spot orders")
    
    def _normalize_position_size(self, perp_position: Any) -> float:
        """Utility to ensure perp_position is always a float."""
        if isinstance(perp_position, dict):
            return perp_position.get('size', 0.0)
        elif isinstance(perp_position, list):
            if perp_position and isinstance(perp_position[0], dict):
                return perp_position[0].get('size', 0.0)
            else:
                return 0.0
        elif isinstance(perp_position, (int, float)):
            return perp_position
        else:
            self.logger.warning(f"Unexpected type for perp_position: {type(perp_position)}")
            return 0.0
    
    def calculate_funding_income(self, perp_position: float, funding_rate: float) -> float:
        """Calculate daily funding income.
        
        Args:
            perp_position: Current perp position size (negative for short)
            funding_rate: Current funding rate
        
        Returns:
            Daily funding income
        """
        try:
            perp_position = self._normalize_position_size(perp_position)
            # Defensive: ensure funding_rate is a float
            if not isinstance(funding_rate, (int, float)):
                self.logger.warning(f"Unexpected type for funding_rate in funding income: {type(funding_rate)}")
                funding_rate = 0.0
            # Log values for debugging
            self.logger.info(f"Calculating funding income: perp_position={perp_position}, funding_rate={funding_rate}")
            # Get current price for calculation
            ticker = self.exchange.get_ticker(self.spot_symbol)
            if not ticker:
                return 0.0
            current_price = ticker['last']
            # Calculate funding income (positive for short positions when funding rate is positive)
            funding_income = abs(perp_position) * current_price * funding_rate
            return funding_income
        except Exception as e:
            self.logger.log_error(e, "Calculating funding income")
            return 0.0
    
    def update_volume_metrics(self, trade_size: float = 0.0) -> None:
        """Update volume tracking metrics.
        
        Args:
            trade_size: Size of recent trade (if any)
        """
        self.reset_daily_volume()
        
        if trade_size > 0:
            self.daily_volume += trade_size
            self.last_trade_time = time.time()
            self.consecutive_no_fills = 0
            self.logger.info(f"Updated daily volume: {self.daily_volume:.2f}/{self.target_daily_volume:.2f} SOL")
        else:
            # Check if we haven't had fills recently
            if time.time() - self.last_trade_time > 300:  # 5 minutes
                self.consecutive_no_fills += 1
    
    def execute_strategy_cycle(self) -> Dict[str, any]:
        """Execute one complete strategy cycle with enhanced volume generation."""
        try:
            step_times = {}
            t0 = time.time()
            
            # Reset daily volume tracking
            self.reset_daily_volume()
            
            # Concurrently fetch ticker, balance, and positions
            ticker_result = {}
            balance_result = {}
            positions_result = {}
            
            def fetch_ticker():
                ticker_result['value'] = self.exchange.get_ticker(self.spot_symbol)
            def fetch_balance():
                balance_result['value'] = self.exchange.get_balance()
            def fetch_positions():
                positions_result['value'] = self.exchange.get_positions()
            
            threads = [
                threading.Thread(target=fetch_ticker),
                threading.Thread(target=fetch_balance),
                threading.Thread(target=fetch_positions)
            ]
            
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            
            step_times['fetch_ticker_balance_positions'] = time.time() - t0
            
            ticker = ticker_result.get('value')
            if not ticker:
                return {'success': False, 'error': 'Unable to get ticker'}
            
            mid_price = ticker['last']
            self.last_mid_price = mid_price
            spot_inventory = balance_result.get('value')
            positions = positions_result.get('value')
            perp_position = 0.0
            if positions:
                for position in positions:
                    if position.get('symbol') == self.perp_symbol:
                        perp_position = position.get('size', 0.0)
                        break
            perp_position = self._normalize_position_size(perp_position)
            # Additional logging for debugging
            self.logger.debug(f"[DEBUG] Pre-funding: perp_position type={type(perp_position)}, value={perp_position}")
            t1 = time.time()
            volatility = self.volatility_calc.calculate_volatility(
                self.spot_symbol,
                self.volatility_config.get('atr_period', 14),
                self.volatility_config.get('timeframe', '1h')
            )
            step_times['volatility'] = time.time() - t1
            
            t2 = time.time()
            funding_rate = self.exchange.get_funding_rate(self.perp_symbol)
            if funding_rate is None:
                funding_rate = self.config.get('funding_rate_annual', 0.08) / 365
            self.logger.debug(f"[DEBUG] Pre-funding: funding_rate type={type(funding_rate)}, value={funding_rate}")
            funding_income = self.calculate_funding_income(perp_position, funding_rate)
            self.logger.debug(f"[DEBUG] Post-funding: funding_income type={type(funding_income)}, value={funding_income}")
            step_times['funding'] = time.time() - t2
            
            t3 = time.time()
            balance = balance_result.get('value')
            positions = positions_result.get('value') or []
            risk_safe, violations = self.risk_manager.comprehensive_risk_check(
                spot_inventory, volatility, balance, positions
            )
            step_times['risk'] = time.time() - t3
            
            if not risk_safe:
                self.cancel_spot_orders()
                return {
                    'success': False,
                    'error': f"Risk violations: {', '.join(violations)}",
                    'trading_paused': True
                }
            
            t4 = time.time()
            
            # Calculate multiple tiers of quotes
            quotes = self.calculate_quotes(mid_price, volatility)
            
            # Place spot quotes across multiple tiers
            spot_order_ids = self.place_spot_quotes(quotes)
            
            # Calculate and place hedge
            required_hedge = self.calculate_hedge_size(spot_inventory)
            hedge_order_id = self.place_hedge_order(required_hedge, perp_position)
            
            # Update volume metrics
            self.update_volume_metrics()
            
            self.risk_manager.increment_trade_count()
            step_times['orders'] = time.time() - t4
            
            self.logger.info(f"Step timings: {step_times}")
            
            return {
                'success': True,
                'mid_price': mid_price,
                'quotes': len(quotes),
                'spread': quotes[0][1] - quotes[0][0] if quotes else 0,
                'volatility': volatility,
                'spot_inventory': spot_inventory,
                'perp_position': perp_position,
                'funding_rate': funding_rate,
                'funding_income': funding_income,
                'spot_orders': len(spot_order_ids),
                'hedge_order': hedge_order_id is not None,
                'risk_safe': risk_safe,
                'daily_volume': self.daily_volume,
                'volume_progress': self.daily_volume / self.target_daily_volume
            }
            
        except Exception as e:
            self.logger.log_error(e, "Strategy cycle execution")
            return {'success': False, 'error': str(e)}
    
    def get_strategy_summary(self) -> Dict[str, any]:
        """Get current strategy summary.
        
        Returns:
            Dictionary with strategy summary
        """
        return {
            'spot_symbol': self.spot_symbol,
            'perp_symbol': self.perp_symbol,
            'current_inventory': self.current_inventory,
            'last_mid_price': self.last_mid_price,
            'base_spread': self.base_spread,
            'inventory_size': self.inventory_size,
            'leverage': self.leverage,
            'spot_orders': len(self.current_spot_orders),
            'perp_orders': len(self.current_perp_orders),
            'daily_volume': self.daily_volume,
            'target_volume': self.target_daily_volume,
            'volume_progress': self.daily_volume / self.target_daily_volume,
            'order_tiers': self.order_tiers,
            'spread_aggression': self.spread_aggression
        } 