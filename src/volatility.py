import numpy as np
from typing import List, Tuple, Optional, Dict, Any
import ccxt
import time
from logger import MarketMakerLogger
from config import ConfigManager

class VolatilityCalculator:
    """Calculates volatility using ATR and adjusts spreads accordingly."""
    
    def __init__(self, config: ConfigManager, logger: MarketMakerLogger):
        """Initialize volatility calculator.
        
        Args:
            config: Configuration manager
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.exchange = None  # Will be set later
        self.atr_cache = {}  # Cache ATR values to avoid repeated calculations
        self.volatility_cache = {}  # Cache volatility calculations
        self.ohlcv_cache = {}  # Cache OHLCV data
        self.cache_ttl = 180  # Increased to 180 seconds TTL for volatility data
        self.ohlcv_cache_ttl = 60  # Increased to 60 seconds TTL for OHLCV data
        
        # Performance monitoring
        self.calculation_times = []
        self.cache_hits = 0
        self.cache_misses = 0
    
    def set_exchange(self, exchange: ccxt.Exchange) -> None:
        """Set the exchange instance for data fetching.
        
        Args:
            exchange: CCXT exchange instance
        """
        self.exchange = exchange
    
    def calculate_true_range(self, high: float, low: float, prev_close: float) -> float:
        """Calculate True Range for a single period.
        
        Args:
            high: High price
            low: Low price
            prev_close: Previous close price
            
        Returns:
            True Range value
        """
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        return max(tr1, tr2, tr3)
    
    def get_cached_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Optional[List]:
        """Get cached OHLCV data if still valid.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe for data
            limit: Number of periods
            
        Returns:
            Cached OHLCV data or None if expired/missing
        """
        cache_key = f"{symbol}_{timeframe}_{limit}"
        if cache_key in self.ohlcv_cache:
            cache_entry = self.ohlcv_cache[cache_key]
            if time.time() - cache_entry['timestamp'] < self.ohlcv_cache_ttl:
                return cache_entry['data']
            else:
                del self.ohlcv_cache[cache_key]
        return None
    
    def cache_ohlcv_data(self, symbol: str, timeframe: str, limit: int, data: List) -> None:
        """Cache OHLCV data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe for data
            limit: Number of periods
            data: OHLCV data to cache
        """
        cache_key = f"{symbol}_{timeframe}_{limit}"
        self.ohlcv_cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def calculate_atr(self, symbol: str, period: int = 14, timeframe: str = '1h') -> float:
        """Calculate Average True Range (ATR) with enhanced caching.
        
        Args:
            symbol: Trading symbol
            period: Number of periods for ATR calculation
            timeframe: Timeframe for OHLCV data
            
        Returns:
            ATR value
        """
        start_time = time.time()
        
        try:
            if not self.exchange:
                self.logger.warning("Exchange not set for volatility calculation")
                return 0.0
            
            # Check cache first
            cache_key = f"{symbol}_{timeframe}_{period}"
            if cache_key in self.atr_cache:
                cache_entry = self.atr_cache[cache_key]
                if time.time() - cache_entry['timestamp'] < self.cache_ttl:
                    self.cache_hits += 1
                    return cache_entry['data']
                else:
                    del self.atr_cache[cache_key]
            
            self.cache_misses += 1
            
            # Check OHLCV cache first
            ohlcv = self.get_cached_ohlcv(symbol, timeframe, period + 1)
            if not ohlcv:
                # Fetch OHLCV data
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=period + 1)
                if ohlcv:
                    self.cache_ohlcv_data(symbol, timeframe, period + 1, ohlcv)
            
            if len(ohlcv) < period + 1:
                self.logger.warning(f"Insufficient data for ATR calculation: {len(ohlcv)} < {period + 1}")
                return 0.0
            
            # Calculate True Range for each period
            true_ranges = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]
                tr = self.calculate_true_range(high, low, prev_close)
                true_ranges.append(tr)
            
            # Calculate ATR as simple moving average of True Range
            atr = np.mean(true_ranges[-period:])
            
            # Cache the result
            self.atr_cache[cache_key] = {
                'data': atr,
                'timestamp': time.time()
            }
            
            # Record calculation time
            duration = time.time() - start_time
            self.calculation_times.append(duration)
            if len(self.calculation_times) > 100:
                self.calculation_times = self.calculation_times[-100:]
            
            self.logger.debug(f"ATR calculated for {symbol}: {atr:.6f} (took {duration:.3f}s)")
            return atr
            
        except Exception as e:
            self.logger.log_error(e, f"ATR calculation for {symbol}")
            return 0.0
    
    def calculate_volatility(self, symbol: str, period: int = 14, timeframe: str = '1h') -> float:
        """Calculate volatility as ATR divided by current price with caching.
        
        Args:
            symbol: Trading symbol
            period: Number of periods for ATR calculation
            timeframe: Timeframe for OHLCV data
            
        Returns:
            Volatility as a decimal (e.g., 0.12 for 12%)
        """
        start_time = time.time()
        
        try:
            if not self.exchange:
                self.logger.warning("Exchange not set for volatility calculation")
                return 0.0
            
            # Check volatility cache first
            cache_key = f"{symbol}_{timeframe}_{period}_vol"
            if cache_key in self.volatility_cache:
                cache_entry = self.volatility_cache[cache_key]
                if time.time() - cache_entry['timestamp'] < self.cache_ttl:
                    self.cache_hits += 1
                    return cache_entry['data']
                else:
                    del self.volatility_cache[cache_key]
            
            self.cache_misses += 1
            
            # Get current price
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            if current_price <= 0:
                self.logger.warning(f"Invalid price for {symbol}: {current_price}")
                return 0.0
            
            # Calculate ATR
            atr = self.calculate_atr(symbol, period, timeframe)
            
            # Calculate volatility
            volatility = atr / current_price
            
            # Cache the result
            self.volatility_cache[cache_key] = {
                'data': volatility,
                'timestamp': time.time()
            }
            
            # Record calculation time
            duration = time.time() - start_time
            self.calculation_times.append(duration)
            if len(self.calculation_times) > 100:
                self.calculation_times = self.calculation_times[-100:]
            
            self.logger.log_volatility(symbol, atr, volatility)
            return volatility
            
        except Exception as e:
            self.logger.log_error(e, f"Volatility calculation for {symbol}")
            return 0.0
    
    def adjust_spread(self, base_spread: float, atr: float, scale_factor: float = 0.5) -> float:
        """Adjust spread based on ATR.
        
        Args:
            base_spread: Base spread as decimal (e.g., 0.00245 for 0.245%)
            atr: Average True Range value
            scale_factor: Factor to scale ATR impact
            
        Returns:
            Adjusted spread as decimal
        """
        try:
            # Adjust spread: spread = base_spread * (1 + k * atr)
            adjusted_spread = base_spread * (1 + scale_factor * atr)
            
            self.logger.debug(f"Spread adjustment: {base_spread:.6f} -> {adjusted_spread:.6f} "
                            f"(ATR: {atr:.6f})")
            
            return adjusted_spread
            
        except Exception as e:
            self.logger.log_error(e, "Spread adjustment")
            return base_spread
    
    def adjust_spread_by_symbol(self, base_spread: float, symbol: str, scale_factor: float = 0.5,
                     period: int = 14, timeframe: str = '1h') -> float:
        """Adjust spread based on volatility for a specific symbol.
        
        Args:
            base_spread: Base spread as decimal (e.g., 0.00245 for 0.245%)
            symbol: Trading symbol
            scale_factor: Factor to scale volatility impact
            period: Number of periods for ATR calculation
            timeframe: Timeframe for OHLCV data
            
        Returns:
            Adjusted spread as decimal
        """
        try:
            volatility = self.calculate_volatility(symbol, period, timeframe)
            
            # Adjust spread: spread = base_spread * (1 + k * volatility)
            adjusted_spread = base_spread * (1 + scale_factor * volatility)
            
            self.logger.debug(f"Spread adjustment: {base_spread:.6f} -> {adjusted_spread:.6f} "
                            f"(volatility: {volatility:.4f})")
            
            return adjusted_spread
            
        except Exception as e:
            self.logger.log_error(e, f"Spread adjustment for {symbol}")
            return base_spread
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self.atr_cache.clear()
        self.volatility_cache.clear()
        self.ohlcv_cache.clear()
        self.logger.debug("Volatility calculator caches cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        avg_calculation_time = np.mean(self.calculation_times) if self.calculation_times else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'avg_calculation_time': avg_calculation_time,
            'atr_cache_size': len(self.atr_cache),
            'volatility_cache_size': len(self.volatility_cache),
            'ohlcv_cache_size': len(self.ohlcv_cache)
        }
    
    def get_market_volatility_status(self, symbol: str, max_volatility: float = 0.24) -> Tuple[bool, float]:
        """Check if market volatility is within acceptable limits.
        
        Args:
            symbol: Trading symbol
            max_volatility: Maximum acceptable volatility
            
        Returns:
            Tuple of (is_safe, volatility)
        """
        volatility = self.calculate_volatility(symbol)
        is_safe = volatility <= max_volatility
        
        if not is_safe:
            self.logger.warning(f"High volatility detected for {symbol}: {volatility:.4f} > {max_volatility}")
        
        return is_safe, volatility
    
    def optimize_calculation_period(self, symbol: str, target_time: float = 0.1) -> int:
        """Optimize calculation period based on performance.
        
        Args:
            symbol: Trading symbol
            target_time: Target calculation time in seconds
            
        Returns:
            Optimized period length
        """
        if not self.calculation_times:
            return 14  # Default period
        
        avg_time = np.mean(self.calculation_times)
        
        if avg_time > target_time * 1.5:
            # Reduce period if calculations are too slow
            return max(7, 14 - 3)
        elif avg_time < target_time * 0.5:
            # Increase period if calculations are very fast
            return min(21, 14 + 3)
        
        return 14  # Keep current period 