import logging
import os
from datetime import datetime
from typing import Optional

class MarketMakerLogger:
    """Comprehensive logging for the market making program."""
    
    def __init__(self, log_dir: str = "logs", log_level: str = "INFO"):
        """Initialize the logger.
        
        Args:
            log_dir: Directory to store log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_dir = log_dir
        self.log_level = getattr(logging, log_level.upper())
        
        # Create logs directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger('market_maker')
        self.logger.setLevel(self.log_level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler for detailed logging
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f'market_maker_{datetime.now().strftime("%Y%m%d")}.log')
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler for user-friendly output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(simple_formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        """Log critical message."""
        self.logger.critical(message)
    
    def log_trade(self, side: str, symbol: str, amount: float, price: float, 
                  order_id: Optional[str] = None) -> None:
        """Log trade information."""
        message = f"TRADE: {side} {amount} {symbol} @ {price}"
        if order_id:
            message += f" (Order ID: {order_id})"
        self.info(message)
    
    def log_quote(self, symbol: str, bid: float, ask: float, spread: float) -> None:
        """Log quote information."""
        self.info(f"QUOTE: {symbol} Bid: {bid}, Ask: {ask}, Spread: {spread:.4f}")
    
    def log_funding_rate(self, symbol: str, rate: float, timestamp: Optional[str] = None) -> None:
        """Log funding rate information."""
        message = f"FUNDING: {symbol} Rate: {rate:.6f}"
        if timestamp:
            message += f" (Time: {timestamp})"
        self.info(message)
    
    def log_volatility(self, symbol: str, atr: float, volatility: float) -> None:
        """Log volatility information."""
        self.info(f"VOLATILITY: {symbol} ATR: {atr:.4f}, Vol: {volatility:.4f}")
    
    def log_inventory(self, symbol: str, inventory: float, pnl: float) -> None:
        """Log inventory and PnL information."""
        self.info(f"INVENTORY: {symbol} Size: {inventory:.4f}, PnL: {pnl:.4f}")
    
    def log_error(self, error: Exception, context: str = "") -> None:
        """Log error with context."""
        message = f"ERROR in {context}: {str(error)}"
        self.error(message)
    
    def cleanup(self) -> None:
        """Clean up logger resources."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler) 