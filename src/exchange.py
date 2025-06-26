import ccxt
from typing import Dict, List, Optional, Tuple, Any
import time
from config import ConfigManager
from logger import MarketMakerLogger
from performance_optimizer import PerformanceOptimizer
import random

class HyperliquidExchange:
    """Interface for Hyperliquid exchange operations."""
    
    def __init__(self, config: ConfigManager, logger: MarketMakerLogger):
        """Initialize exchange interface.
        
        Args:
            config: Configuration manager
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.exchange = None
        self.connected = False
        self.markets = {}  # Cache for market information
        self.performance_optimizer = PerformanceOptimizer(config, logger)
        self._initialize_exchange()
    
    def _initialize_exchange(self) -> None:
        """Initialize the CCXT exchange instance."""
        try:
            exchange_config = self.config.get_exchange_config()
            
            # Initialize CCXT exchange with Hyperliquid-specific configuration
            self.exchange = getattr(ccxt, exchange_config['name'])({
                'apiKey': exchange_config['api_wallet'],  # API wallet address
                'secret': exchange_config['api_wallet_private'],  # API wallet private key
                'wallet': exchange_config['main_wallet'],  # Main wallet address
                'sandbox': False,  # Set to True for testing
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',  # Default to spot trading
                }
            })
            
            self.logger.info(f"Initialized {exchange_config['name']} exchange")
            
        except Exception as e:
            self.logger.log_error(e, "Exchange initialization")
            raise
    
    def connect(self) -> bool:
        """Connect to the exchange and verify credentials."""
        try:
            # Test connection by fetching markets and account info
            self.exchange.load_markets()
            self.markets = self.exchange.markets  # Cache markets for later use
            
            # Test balance fetch to verify credentials
            exchange_config = self.config.get_exchange_config()
            main_wallet = exchange_config.get('main_wallet')
            if not main_wallet:
                raise ValueError("Main wallet address is not set in config.")
            self.exchange.fetch_balance(params={'user': main_wallet})
            self.connected = True
            self.logger.info("Successfully connected to Hyperliquid")
            
            # Log available markets for debugging
            self._log_available_markets()
            
            return True
            
        except Exception as e:
            self.logger.log_error(e, "Exchange connection")
            self.connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if the exchange is connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.connected
    
    def _log_available_markets(self) -> None:
        """Log available markets for debugging purposes."""
        try:
            spot_markets = [symbol for symbol, market in self.markets.items() 
                          if market.get('type') == 'spot']
            swap_markets = [symbol for symbol, market in self.markets.items() 
                          if market.get('type') == 'swap']
            
            self.logger.info(f"Available spot markets: {len(spot_markets)}")
            self.logger.info(f"Available swap markets: {len(swap_markets)}")
            
            # Log SOL-related markets specifically
            sol_spot = [m for m in spot_markets if 'SOL' in m]
            sol_swap = [m for m in swap_markets if 'SOL' in m]
            
            if sol_spot:
                self.logger.info(f"SOL spot markets: {sol_spot}")
            if sol_swap:
                self.logger.info(f"SOL swap markets: {sol_swap}")
                
        except Exception as e:
            self.logger.log_error(e, "Logging available markets")
    
    def get_market_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get market information for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'SOL/USDC')
            
        Returns:
            Market information dictionary
        """
        try:
            if not self.connected:
                self.logger.warning("Exchange not connected")
                return None
            
            # Use cached markets if available, otherwise fetch
            if symbol in self.markets:
                return self.markets[symbol]
            
            # Fallback to direct market fetch
            market = self.exchange.market(symbol)
            return market
            
        except Exception as e:
            self.logger.log_error(e, f"Getting market info for {symbol}")
            return None
    
    def find_solana_markets(self) -> Tuple[Optional[str], Optional[str]]:
        """Find USOL/USDC spot and SOL/USDC:USDC perpetual markets strictly."""
        try:
            if not self.connected:
                self.logger.warning("Exchange not connected")
                return None, None

            spot_markets = [symbol for symbol, market in self.markets.items() if market.get('type') == 'spot']
            swap_markets = [symbol for symbol, market in self.markets.items() if market.get('type') == 'swap']
            self.logger.info(f"Available spot markets: {spot_markets}")
            self.logger.info(f"Available swap markets: {swap_markets}")

            spot_symbol = None
            perp_symbol = None

            for symbol in spot_markets:
                if symbol.upper() == 'USOL/USDC':
                    spot_symbol = symbol
                    break
            for symbol in swap_markets:
                if symbol.upper() == 'SOL/USDC:USDC':
                    perp_symbol = symbol
                    break

            if not spot_symbol:
                self.logger.error("USOL/USDC spot market not found. Please check available spot markets.")
            else:
                self.logger.info(f"Found USOL/USDC spot market: {spot_symbol}")
            if not perp_symbol:
                self.logger.error("SOL/USDC:USDC perpetual market not found. Please check available swap markets.")
            else:
                self.logger.info(f"Found SOL/USDC:USDC perpetual market: {perp_symbol}")

            return spot_symbol, perp_symbol
        except Exception as e:
            self.logger.log_error(e, "Finding SOL markets")
            return None, None
    
    def _retry_api_call(self, func, *args, max_retries=3, base_delay=0.2, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) * (1 + random.uniform(-0.2, 0.2))
                self.logger.warning(f"Retrying API call due to error: {e} (attempt {attempt+1})")
                time.sleep(delay)
    
    def get_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current ticker information with caching.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Ticker information dictionary
        """
        @self.performance_optimizer.time_operation('get_ticker')
        def _get_ticker():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                cached_ticker = self.performance_optimizer.get_cached_price(symbol)
                if cached_ticker:
                    return cached_ticker
                if not self.performance_optimizer.rate_limit_api_call('get_ticker'):
                    time.sleep(0.05)
                start_time = time.time()
                ticker = self._retry_api_call(self.exchange.fetch_ticker, symbol)
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('get_ticker', duration)
                if ticker:
                    self.performance_optimizer.cache_price_data(symbol, ticker)
                return ticker
            except Exception as e:
                self.logger.log_error(e, f"Getting ticker for {symbol}")
                return None
        return _get_ticker()
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Get order book for a symbol with caching.
        
        Args:
            symbol: Trading symbol
            limit: Number of orders to fetch
            
        Returns:
            Order book dictionary
        """
        @self.performance_optimizer.time_operation('get_order_book')
        def _get_order_book():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                cached_order_book = self.performance_optimizer.get_cached_order_book(symbol)
                if cached_order_book:
                    return cached_order_book
                if not self.performance_optimizer.rate_limit_api_call('get_order_book'):
                    time.sleep(0.05)
                start_time = time.time()
                order_book = self._retry_api_call(self.exchange.fetch_order_book, symbol, limit)
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('get_order_book', duration)
                if order_book:
                    self.performance_optimizer.cache_order_book(symbol, order_book)
                return order_book
            except Exception as e:
                self.logger.log_error(e, f"Getting order book for {symbol}")
                return None
        return _get_order_book()
    
    def get_balance(self) -> Optional[Dict[str, Any]]:
        """Get account balance.
        
        Returns:
            Balance dictionary
        """
        @self.performance_optimizer.time_operation('get_balance')
        def _get_balance():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                exchange_config = self.config.get_exchange_config()
                main_wallet = exchange_config.get('main_wallet')
                if not main_wallet:
                    self.logger.warning("Main wallet address is not set in config.")
                    return None
                if not self.performance_optimizer.rate_limit_api_call('get_balance'):
                    time.sleep(0.05)
                start_time = time.time()
                balance = self._retry_api_call(self.exchange.fetch_balance, params={'user': main_wallet})
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('get_balance', duration)
                return balance
            except Exception as e:
                self.logger.log_error(e, "Getting balance")
                return None
        return _get_balance()
    
    def get_positions(self) -> Optional[List[Dict[str, Any]]]:
        """Get current positions.
        
        Returns:
            List of position dictionaries
        """
        @self.performance_optimizer.time_operation('get_positions')
        def _get_positions():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                main_wallet = self.config.get('exchange.main_wallet')
                if not main_wallet:
                    self.logger.warning("Main wallet address is not set in config.")
                    return None
                if not self.performance_optimizer.rate_limit_api_call('get_positions'):
                    time.sleep(0.05)
                self.exchange.options['defaultType'] = 'swap'
                start_time = time.time()
                positions = self._retry_api_call(self.exchange.fetch_positions, params={'user': main_wallet})
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('get_positions', duration)
                self.exchange.options['defaultType'] = 'spot'
                return positions
            except Exception as e:
                self.logger.log_error(e, "Getting positions")
                return None
        return _get_positions()
    
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Get current funding rate for a perpetual contract.
        
        Args:
            symbol: Trading symbol (should be perpetual contract)
            
        Returns:
            Funding rate as decimal
        """
        @self.performance_optimizer.time_operation('get_funding_rate')
        def _get_funding_rate():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                if not self.performance_optimizer.rate_limit_api_call('get_funding_rate'):
                    time.sleep(0.05)
                self.exchange.options['defaultType'] = 'swap'
                start_time = time.time()
                funding_info = self._retry_api_call(self.exchange.fetch_funding_rate, symbol)
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('get_funding_rate', duration)
                self.exchange.options['defaultType'] = 'spot'
                if funding_info and 'fundingRate' in funding_info:
                    rate = funding_info['fundingRate']
                    self.logger.log_funding_rate(symbol, rate)
                    return rate
                return None
            except Exception as e:
                self.logger.log_error(e, f"Getting funding rate for {symbol}")
                return None
        return _get_funding_rate()
    
    def place_order(self, symbol: str, side: str, amount: float, price: float = None, 
                   order_type: str = 'limit', market_type: str = 'spot',
                   time_in_force: str = None, post_only: bool = None, reduce_only: bool = None,
                   trigger_price: float = None, client_order_id: str = None, slippage: str = None,
                   vault_address: str = None, extra_params: dict = None) -> Optional[str]:
        """
        Place an order with full Hyperliquid/CCXT parameter support.
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            amount: Order amount
            price: Order price (None for market orders)
            order_type: 'limit' or 'market'
            market_type: 'spot' or 'swap'
            time_in_force: 'Gtc', 'Ioc', 'Alo', etc.
            post_only: True/False for post-only
            reduce_only: True/False for reduce-only
            trigger_price: Trigger price for stop/trigger orders
            client_order_id: Optional client order id (cloid)
            slippage: Slippage for market order
            vault_address: Vault address for subaccount/vault trading
            extra_params: Any additional params to pass to the API
        Returns:
            Order ID if successful, None otherwise
        """
        @self.performance_optimizer.time_operation('place_order')
        def _place_order():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                # Ensure API wallet and private key are present for signing orders
                exchange_config = self.config.get_exchange_config()
                api_wallet = exchange_config.get('api_wallet')
                api_wallet_private = exchange_config.get('api_wallet_private')
                if not api_wallet or not api_wallet_private:
                    self.logger.error("API wallet and private key must be set for order signing (see Hyperliquid docs)")
                    return None
                if not self.performance_optimizer.rate_limit_api_call('place_order'):
                    time.sleep(0.05)
                self.exchange.options['defaultType'] = market_type
                # Build params dict for Hyperliquid/CCXT
                params = extra_params.copy() if extra_params else {}
                if time_in_force:
                    params['timeInForce'] = time_in_force
                if post_only is not None:
                    params['postOnly'] = post_only
                if reduce_only is not None:
                    params['reduceOnly'] = reduce_only
                if trigger_price is not None:
                    params['triggerPrice'] = trigger_price
                if client_order_id:
                    params['clientOrderId'] = client_order_id
                if slippage:
                    params['slippage'] = slippage
                if vault_address:
                    params['vaultAddress'] = vault_address
                # Place order
                start_time = time.time()
                order = self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('place_order', duration)
                self.exchange.options['defaultType'] = 'spot'
                order_id = order.get('id')
                if order_id:
                    self.logger.log_trade(side, symbol, amount, price, order_id)
                return order_id
            except Exception as e:
                self.logger.log_error(e, f"Placing {side} order for {symbol}")
                return None
        return _place_order()
    
    def cancel_order(self, order_id: str, symbol: str, market_type: str = 'spot',
                    asset: int = None, vault_address: str = None, extra_params: dict = None) -> bool:
        """
        Cancel an order with full Hyperliquid/CCXT parameter support.
        Args:
            order_id: Order ID to cancel
            symbol: Trading symbol
            market_type: 'spot' or 'swap'
            asset: Asset index (if required by API)
            vault_address: Vault address for subaccount/vault cancellation
            extra_params: Any additional params to pass to the API
        Returns:
            True if successful, False otherwise
        """
        @self.performance_optimizer.time_operation('cancel_order')
        def _cancel_order():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return False
                if not self.performance_optimizer.rate_limit_api_call('cancel_order'):
                    time.sleep(0.05)
                self.exchange.options['defaultType'] = market_type
                # Build params dict for Hyperliquid/CCXT
                params = extra_params.copy() if extra_params else {}
                if asset is not None:
                    params['a'] = asset
                if vault_address:
                    params['vaultAddress'] = vault_address
                # Hyperliquid expects 'a' (asset) and 'o' (order id) in the cancels list
                params['cancels'] = [{
                    'a': asset if asset is not None else symbol,
                    'o': int(order_id)
                }]
                # Place cancel order
                start_time = time.time()
                # Some CCXT implementations use cancel_order, others use create_order with type 'cancel'
                try:
                    result = self.exchange.cancel_order(order_id, symbol, params=params)
                except Exception:
                    # Fallback to create_order with type 'cancel' if needed
                    result = self.exchange.create_order(
                        symbol=symbol,
                        type='cancel',
                        side=None,
                        amount=None,
                        price=None,
                        params=params
                    )
                duration = time.time() - start_time
                self.performance_optimizer.record_api_call('cancel_order', duration)
                self.exchange.options['defaultType'] = 'spot'
                self.logger.info(f"Cancelled order {order_id} for {symbol}")
                return True
            except Exception as e:
                self.logger.log_error(e, f"Cancelling order {order_id}")
                return False
        return _cancel_order()
    
    def get_open_orders(self, symbol: str = None, market_type: str = 'spot') -> Optional[List[Dict[str, Any]]]:
        """Get open orders with performance monitoring.
        
        Args:
            symbol: Trading symbol (optional)
            market_type: 'spot' or 'swap'
            
        Returns:
            List of open orders
        """
        # Apply performance timing decorator
        @self.performance_optimizer.time_operation('get_open_orders')
        def _get_open_orders():
            try:
                if not self.connected:
                    self.logger.warning("Exchange not connected")
                    return None
                
                # Rate limiting
                if not self.performance_optimizer.rate_limit_api_call('get_open_orders'):
                    time.sleep(0.05)  # Wait 50ms
                
                # Set market type
                self.exchange.options['defaultType'] = market_type
                
                # Get open orders
                start_time = time.time()
                orders = self.exchange.fetch_open_orders(symbol)
                duration = time.time() - start_time
                
                # Record API call timing
                self.performance_optimizer.record_api_call('get_open_orders', duration)
                
                # Reset to spot
                self.exchange.options['defaultType'] = 'spot'
                
                return orders
                
            except Exception as e:
                self.logger.log_error(e, "Getting open orders")
                return None
        
        return _get_open_orders()
    
    def get_symbol_for_perp(self, spot_symbol: str) -> str:
        """Convert spot symbol to perpetual symbol for Hyperliquid."""
        # Robust mapping for USOL/USDC <-> SOL/USDC:USDC
        spot_symbol_upper = spot_symbol.upper()
        for symbol, market in self.markets.items():
            if market.get('type') == 'swap' and (
                symbol.upper() == 'SOL/USDC:USDC' or
                (spot_symbol_upper == 'USOL/USDC' and symbol.upper() == 'SOL/USDC:USDC')
            ):
                return symbol
        if spot_symbol_upper == 'USOL/USDC':
            return 'SOL/USDC:USDC'
        if ':' not in spot_symbol:
            return f"{spot_symbol}:USDC"
        return spot_symbol
    
    def get_symbol_for_spot(self, perp_symbol: str) -> str:
        """Convert perpetual symbol to spot symbol."""
        perp_symbol_upper = perp_symbol.upper()
        for symbol, market in self.markets.items():
            if market.get('type') == 'spot' and (
                symbol.upper() == 'USOL/USDC' or
                (perp_symbol_upper == 'SOL/USDC:USDC' and symbol.upper() == 'USOL/USDC')
            ):
                return symbol
        if perp_symbol_upper == 'SOL/USDC:USDC':
            return 'USOL/USDC'
        if ':' in perp_symbol:
            return perp_symbol.split(':')[0]
        return perp_symbol
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics from the optimizer.
        
        Returns:
            Dictionary with performance statistics
        """
        return self.performance_optimizer.get_performance_stats()
    
    def clear_performance_cache(self) -> None:
        """Clear performance optimizer cache."""
        self.performance_optimizer.clear_cache() 