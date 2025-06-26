import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from config import ConfigManager
from exchange import HyperliquidExchange
from volatility import VolatilityCalculator
from risk_manager import RiskManager
from logger import MarketMakerLogger

class MarketMakingStrategy:
    """Implements the long spot, short perps market making strategy."""
    
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
        
        # Strategy state - will be set after market discovery
        self.spot_symbol = None
        self.perp_symbol = None
        self.base_spread = self.asset_config['base_spread']
        self.inventory_size = self.asset_config['inventory_size']
        self.leverage = self.asset_config['leverage']
        
        # Current state
        self.current_inventory = 0.0
        self.current_spot_orders = []
        self.current_perp_orders = []
        self.last_mid_price = 0.0
        
        # Discover markets
        self._discover_markets()
        
        self.logger.info(f"Initialized strategy for {self.spot_symbol} (perp: {self.perp_symbol})")
    
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
    
    def calculate_quotes(self, mid_price: float, volatility: float) -> Tuple[float, float, float]:
        """Calculate bid and ask prices based on mid price and volatility.
        
        Args:
            mid_price: Current mid price
            volatility: Current volatility measure
            
        Returns:
            Tuple of (bid_price, ask_price, spread)
        """
        try:
            # Calculate ATR for spread adjustment
            atr = self.volatility_calc.calculate_atr(
                self.spot_symbol,
                self.volatility_config.get('atr_period', 14),
                self.volatility_config.get('timeframe', '1h')
            )
            
            # Adjust spread based on ATR
            adjusted_spread = self.volatility_calc.adjust_spread(
                self.base_spread,
                atr,
                self.volatility_config.get('spread_scale_factor', 0.5)
            )
            
            # Calculate bid and ask prices
            spread_half = adjusted_spread / 2
            bid_price = mid_price * (1 - spread_half)
            ask_price = mid_price * (1 + spread_half)
            
            self.logger.log_quote(self.spot_symbol, bid_price, ask_price, adjusted_spread)
            
            return bid_price, ask_price, adjusted_spread
            
        except Exception as e:
            self.logger.log_error(e, "Quote calculation")
            # Fallback to base spread
            spread_half = self.base_spread / 2
            bid_price = mid_price * (1 - spread_half)
            ask_price = mid_price * (1 + spread_half)
            return bid_price, ask_price, self.base_spread
    
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
    
    def place_spot_quotes(self, bid_price: float, ask_price: float, 
                         order_size: float) -> List[str]:
        """Place spot market making quotes.
        
        Args:
            bid_price: Bid price
            ask_price: Ask price
            order_size: Size for each order
            
        Returns:
            List of order IDs
        """
        order_ids = []
        
        try:
            # Cancel existing spot orders
            self.cancel_spot_orders()
            
            # Place new bid order
            if order_size > 0:
                bid_order_id = self.exchange.place_order(
                    self.spot_symbol, 'buy', order_size, bid_price, 'limit', 'spot'
                )
                if bid_order_id:
                    order_ids.append(bid_order_id)
                    self.current_spot_orders.append(bid_order_id)
            
            # Place new ask order
            if order_size > 0:
                ask_order_id = self.exchange.place_order(
                    self.spot_symbol, 'sell', order_size, ask_price, 'limit', 'spot'
                )
                if ask_order_id:
                    order_ids.append(ask_order_id)
                    self.current_spot_orders.append(ask_order_id)
            
            self.logger.info(f"Placed {len(order_ids)} spot orders")
            
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
    
    def calculate_funding_income(self, perp_position: float, funding_rate: float) -> float:
        """Calculate daily funding income.
        
        Args:
            perp_position: Current perp position size (negative for short)
            funding_rate: Current funding rate
            
        Returns:
            Daily funding income
        """
        try:
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
    
    def execute_strategy_cycle(self) -> Dict[str, any]:
        """Execute one complete strategy cycle with concurrent API calls and profiling."""
        try:
            step_times = {}
            t0 = time.time()
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
            perp_position = positions_result.get('value')
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
            funding_income = self.calculate_funding_income(perp_position, funding_rate)
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
            bid_price, ask_price, spread = self.calculate_quotes(mid_price, volatility)
            order_size = self.inventory_size / 2
            spot_order_ids = self.place_spot_quotes(bid_price, ask_price, order_size)
            required_hedge = self.calculate_hedge_size(spot_inventory)
            hedge_order_id = self.place_hedge_order(required_hedge, perp_position)
            self.risk_manager.increment_trade_count()
            step_times['orders'] = time.time() - t4
            self.logger.info(f"Step timings: {step_times}")
            return {
                'success': True,
                'mid_price': mid_price,
                'bid_price': bid_price,
                'ask_price': ask_price,
                'spread': spread,
                'volatility': volatility,
                'spot_inventory': spot_inventory,
                'perp_position': perp_position,
                'funding_rate': funding_rate,
                'funding_income': funding_income,
                'spot_orders': len(spot_order_ids),
                'hedge_order': hedge_order_id is not None,
                'risk_safe': risk_safe
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
            'perp_orders': len(self.current_perp_orders)
        } 