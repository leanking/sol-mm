import asyncio
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from collections import deque
import numpy as np
from logger import MarketMakerLogger
from config import ConfigManager

class PerformanceOptimizer:
    """Performance optimization utilities for market making system."""
    
    def __init__(self, config: ConfigManager, logger: MarketMakerLogger):
        """Initialize performance optimizer.
        
        Args:
            config: Configuration manager
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        
        # Performance monitoring
        self.operation_times = {}
        self.api_call_count = 0
        self.api_call_times = deque(maxlen=1000)
        
        # Caching
        self.price_cache = {}
        self.price_cache_ttl = 1.0  # Increased to 1s TTL for price data
        self.order_book_cache = {}
        self.order_book_cache_ttl = 2.0  # Increased to 2s TTL for order book
        
        # Rate limiting
        self.last_api_call = {}
        self.min_api_interval = 0.05  # 50ms minimum between API calls
        
        # Batch operations
        self.pending_orders = []
        self.batch_size = 5
        self.batch_timeout = 0.1  # 100ms batch timeout
        
        # Performance thresholds
        self.max_ticker_response_time = 0.5  # 500ms
        self.max_order_response_time = 1.0   # 1 second
        self.max_volatility_calc_time = 0.1  # 100ms
        
        self.logger.info("Performance optimizer initialized")
    
    def time_operation(self, operation_name: str) -> Callable:
        """Decorator to time operations.
        
        Args:
            operation_name: Name of the operation being timed
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    # Store timing data
                    if operation_name not in self.operation_times:
                        self.operation_times[operation_name] = []
                    self.operation_times[operation_name].append(duration)
                    
                    # Keep only last 100 measurements
                    if len(self.operation_times[operation_name]) > 100:
                        self.operation_times[operation_name] = self.operation_times[operation_name][-100:]
                    
                    # Log slow operations
                    if duration > self._get_threshold(operation_name):
                        self.logger.warning(f"Slow operation detected: {operation_name} took {duration:.3f}s")
                    
                    return result
                except Exception as e:
                    end_time = time.time()
                    duration = end_time - start_time
                    self.logger.error(f"Operation {operation_name} failed after {duration:.3f}s: {e}")
                    raise
            return wrapper
        return decorator
    
    def _get_threshold(self, operation_name: str) -> float:
        """Get performance threshold for an operation.
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Threshold in seconds
        """
        thresholds = {
            'get_ticker': self.max_ticker_response_time,
            'get_order_book': self.max_ticker_response_time,
            'place_order': self.max_order_response_time,
            'cancel_order': self.max_order_response_time,
            'calculate_volatility': self.max_volatility_calc_time,
            'calculate_atr': self.max_volatility_calc_time
        }
        return thresholds.get(operation_name, 1.0)
    
    def cache_price_data(self, symbol: str, price_data: Dict[str, Any]) -> None:
        """Cache price data with TTL.
        
        Args:
            symbol: Trading symbol
            price_data: Price data to cache
        """
        self.price_cache[symbol] = {
            'data': price_data,
            'timestamp': time.time()
        }
    
    def get_cached_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached price data if still valid.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Cached price data or None if expired/missing
        """
        if symbol in self.price_cache:
            cache_entry = self.price_cache[symbol]
            if time.time() - cache_entry['timestamp'] < self.price_cache_ttl:
                return cache_entry['data']
            else:
                del self.price_cache[symbol]
        return None
    
    def cache_order_book(self, symbol: str, order_book: Dict[str, Any]) -> None:
        """Cache order book data with TTL.
        
        Args:
            symbol: Trading symbol
            order_book: Order book data to cache
        """
        self.order_book_cache[symbol] = {
            'data': order_book,
            'timestamp': time.time()
        }
    
    def get_cached_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached order book data if still valid.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Cached order book data or None if expired/missing
        """
        if symbol in self.order_book_cache:
            cache_entry = self.order_book_cache[symbol]
            if time.time() - cache_entry['timestamp'] < self.order_book_cache_ttl:
                return cache_entry['data']
            else:
                del self.order_book_cache[symbol]
        return None
    
    def rate_limit_api_call(self, operation: str) -> bool:
        """Check if enough time has passed for API call rate limiting.
        
        Args:
            operation: API operation name
            
        Returns:
            True if call is allowed, False if should wait
        """
        current_time = time.time()
        if operation in self.last_api_call:
            time_since_last = current_time - self.last_api_call[operation]
            if time_since_last < self.min_api_interval:
                return False
        
        self.last_api_call[operation] = current_time
        return True
    
    def record_api_call(self, operation: str, duration: float) -> None:
        """Record API call timing for monitoring.
        
        Args:
            operation: API operation name
            duration: Call duration in seconds
        """
        self.api_call_count += 1
        self.api_call_times.append({
            'operation': operation,
            'duration': duration,
            'timestamp': time.time()
        })
    
    def add_to_batch(self, order_data: Dict[str, Any]) -> None:
        """Add order to batch processing queue.
        
        Args:
            order_data: Order data to batch
        """
        self.pending_orders.append(order_data)
    
    def get_batch_orders(self) -> List[Dict[str, Any]]:
        """Get orders ready for batch processing.
        
        Args:
            List of orders to process in batch
        """
        if len(self.pending_orders) >= self.batch_size:
            batch = self.pending_orders[:self.batch_size]
            self.pending_orders = self.pending_orders[self.batch_size:]
            return batch
        return []
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self.price_cache.clear()
        self.order_book_cache.clear()
        self.logger.debug("Performance optimizer caches cleared")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics.
        
        Returns:
            Dictionary with performance statistics
        """
        stats = {
            'api_call_count': self.api_call_count,
            'cache_hit_rates': {},
            'operation_averages': {},
            'slow_operations': []
        }
        
        # Calculate operation averages
        for operation, times in self.operation_times.items():
            if times:
                stats['operation_averages'][operation] = {
                    'mean': np.mean(times),
                    'median': np.median(times),
                    'max': np.max(times),
                    'min': np.min(times),
                    'count': len(times)
                }
        
        # Identify slow operations
        for operation, times in self.operation_times.items():
            if times and np.mean(times) > self._get_threshold(operation):
                stats['slow_operations'].append({
                    'operation': operation,
                    'avg_time': np.mean(times),
                    'threshold': self._get_threshold(operation)
                })
        
        return stats
    
    def optimize_update_interval(self, current_interval: float, 
                               avg_cycle_time: float) -> float:
        """Optimize update interval based on performance.
        
        Args:
            current_interval: Current update interval
            avg_cycle_time: Average cycle execution time
            
        Returns:
            Optimized update interval
        """
        # If cycles are taking longer than the interval, increase it
        if avg_cycle_time > current_interval * 0.8:
            new_interval = max(current_interval * 1.2, avg_cycle_time * 1.1)
            self.logger.info(f"Optimizing interval: {current_interval}s -> {new_interval:.1f}s")
            return new_interval
        
        # If cycles are much faster, we can decrease the interval
        elif avg_cycle_time < current_interval * 0.3:
            new_interval = max(current_interval * 0.8, 1.0)  # Minimum 1 second
            self.logger.info(f"Optimizing interval: {current_interval}s -> {new_interval:.1f}s")
            return new_interval
        
        return current_interval
    
    def should_skip_cycle(self, last_cycle_time: float, 
                         current_volatility: float) -> bool:
        """Determine if a cycle should be skipped for performance reasons.
        
        Args:
            last_cycle_time: Time taken by last cycle
            current_volatility: Current market volatility
            
        Returns:
            True if cycle should be skipped
        """
        # Skip if last cycle took too long
        if last_cycle_time > 2.0:  # More than 2 seconds
            return True
        
        # Skip if volatility is very low (less need for frequent updates)
        if current_volatility < 0.01:  # Less than 1%
            return True
        
        return False
    
    def get_recommendations(self) -> List[str]:
        """Get performance optimization recommendations.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        stats = self.get_performance_stats()
        
        # Check for slow operations
        for slow_op in stats['slow_operations']:
            recommendations.append(
                f"Optimize {slow_op['operation']}: "
                f"{slow_op['avg_time']:.3f}s avg (threshold: {slow_op['threshold']:.3f}s)"
            )
        
        # Check API call frequency
        if self.api_call_count > 1000:
            recommendations.append(
                "High API call count detected - consider implementing more aggressive caching"
            )
        
        # Check cache effectiveness
        if len(self.price_cache) == 0:
            recommendations.append(
                "Price cache is empty - consider enabling caching for better performance"
            )
        
        return recommendations 