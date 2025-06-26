import time
from typing import Dict, List, Optional, Tuple, Any
from config import ConfigManager
from logger import MarketMakerLogger

class RiskManager:
    """Manages risk controls and trading limits."""
    
    def __init__(self, config: ConfigManager, logger: MarketMakerLogger):
        """Initialize risk manager.
        
        Args:
            config: Configuration manager
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.risk_config = config.get_risk_config()
        self.trading_paused = False
        self.pause_reason = ""
        
        # Risk metrics tracking
        self.current_inventory = 0.0
        self.current_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_date = None
        
    def check_inventory_limits(self, inventory: float) -> Tuple[bool, str]:
        """Check if inventory is within acceptable limits.
        
        Args:
            inventory: Current inventory size
            
        Returns:
            Tuple of (is_safe, reason)
        """
        max_inventory = self.risk_config.get('max_inventory', 10.0)
        
        if abs(inventory) > max_inventory:
            reason = f"Inventory {inventory:.4f} exceeds limit {max_inventory}"
            return False, reason
        
        return True, ""
    
    def check_volatility_limits(self, volatility: float) -> Tuple[bool, str]:
        """Check if volatility is within acceptable limits.
        
        Args:
            volatility: Current volatility measure
            
        Returns:
            Tuple of (is_safe, reason)
        """
        max_volatility = self.risk_config.get('max_volatility', 0.24)
        
        if volatility > max_volatility:
            reason = f"Volatility {volatility:.4f} exceeds limit {max_volatility}"
            return False, reason
        
        return True, ""
    
    def check_margin_requirements(self, balance: Dict, positions: List[Dict]) -> Tuple[bool, str]:
        """Check if margin requirements are met.
        
        Args:
            balance: Account balance
            positions: Current positions
            
        Returns:
            Tuple of (is_safe, reason)
        """
        try:
            # Calculate total margin used
            total_margin = 0.0
            for position in positions:
                if position.get('size', 0) != 0:  # Only consider open positions
                    margin = abs(position.get('notional', 0) / position.get('leverage', 1))
                    total_margin += margin
            
            # Get available balance (assuming USDC)
            available_balance = balance.get('USDC', {}).get('free', 0.0)
            margin_buffer = self.risk_config.get('margin_buffer', 2.0)
            
            # Check if we have enough margin buffer
            if total_margin * margin_buffer > available_balance:
                reason = f"Insufficient margin: {available_balance:.2f} < {total_margin * margin_buffer:.2f}"
                return False, reason
            
            return True, ""
            
        except Exception as e:
            self.logger.log_error(e, "Margin requirement check")
            return False, f"Error checking margin: {str(e)}"
    
    def check_daily_trade_limit(self) -> Tuple[bool, str]:
        """Check if daily trade limit has been reached.
        
        Returns:
            Tuple of (is_safe, reason)
        """
        trading_config = self.config.get_trading_config()
        max_trades = trading_config.get('trades_per_day', 100)
        
        if self.daily_trades >= max_trades:
            reason = f"Daily trade limit reached: {self.daily_trades}/{max_trades}"
            return False, reason
        
        return True, ""
    
    def update_inventory(self, inventory: float) -> None:
        """Update current inventory tracking.
        
        Args:
            inventory: New inventory size
        """
        self.current_inventory = inventory
        self.logger.debug(f"Updated inventory: {inventory:.4f}")
    
    def update_pnl(self, pnl: float) -> None:
        """Update current PnL tracking.
        
        Args:
            pnl: New PnL value
        """
        self.current_pnl = pnl
        self.logger.debug(f"Updated PnL: {pnl:.4f}")
    
    def increment_trade_count(self) -> None:
        """Increment daily trade counter."""
        self.daily_trades += 1
        self.logger.debug(f"Trade count: {self.daily_trades}")
    
    def reset_daily_metrics(self) -> None:
        """Reset daily trading metrics."""
        from datetime import datetime
        
        current_date = datetime.now().date()
        if self.last_reset_date != current_date:
            self.daily_trades = 0
            self.last_reset_date = current_date
            self.logger.info("Reset daily trading metrics")
    
    def pause_trading(self, reason: str) -> None:
        """Pause trading due to risk violation.
        
        Args:
            reason: Reason for pausing
        """
        self.trading_paused = True
        self.pause_reason = reason
        self.logger.warning(f"Trading paused: {reason}")
    
    def resume_trading(self) -> None:
        """Resume trading after risk conditions improve."""
        self.trading_paused = False
        self.pause_reason = ""
        self.logger.info("Trading resumed")
    
    def is_trading_allowed(self) -> bool:
        """Check if trading is currently allowed.
        
        Returns:
            True if trading is allowed, False otherwise
        """
        return not self.trading_paused
    
    def get_pause_reason(self) -> str:
        """Get the reason why trading is paused.
        
        Returns:
            Pause reason string
        """
        return self.pause_reason
    
    def get_max_position_size(self) -> float:
        """Get maximum allowed position size.
        
        Returns:
            Maximum position size
        """
        return self.risk_config.get('max_inventory', 10.0)
    
    def get_max_drawdown(self) -> float:
        """Get maximum allowed drawdown.
        
        Returns:
            Maximum drawdown as a decimal (e.g., 0.1 for 10%)
        """
        return self.risk_config.get('max_drawdown', 0.1)
    
    def comprehensive_risk_check(self, inventory: float, volatility: float, 
                               balance: Dict, positions: List[Dict]) -> Tuple[bool, List[str]]:
        """Perform comprehensive risk check.
        
        Args:
            inventory: Current inventory
            volatility: Current volatility
            balance: Account balance
            positions: Current positions
            
        Returns:
            Tuple of (is_safe, list_of_violations)
        """
        violations = []
        
        # Reset daily metrics if needed
        self.reset_daily_metrics()
        
        # Check inventory limits
        inventory_safe, inventory_reason = self.check_inventory_limits(inventory)
        if not inventory_safe:
            violations.append(inventory_reason)
        
        # Check volatility limits
        volatility_safe, volatility_reason = self.check_volatility_limits(volatility)
        if not volatility_safe:
            violations.append(volatility_reason)
        
        # Check margin requirements
        margin_safe, margin_reason = self.check_margin_requirements(balance, positions)
        if not margin_safe:
            violations.append(margin_reason)
        
        # Check daily trade limit
        trade_limit_safe, trade_limit_reason = self.check_daily_trade_limit()
        if not trade_limit_safe:
            violations.append(trade_limit_reason)
        
        # Update tracking
        self.update_inventory(inventory)
        
        # Determine if trading should be paused
        if violations:
            self.pause_trading("; ".join(violations))
        else:
            self.resume_trading()
        
        return len(violations) == 0, violations
    
    def get_risk_summary(self) -> Dict[str, any]:
        """Get current risk metrics summary.
        
        Returns:
            Dictionary of risk metrics
        """
        return {
            'trading_paused': self.trading_paused,
            'pause_reason': self.pause_reason,
            'current_inventory': self.current_inventory,
            'current_pnl': self.current_pnl,
            'daily_trades': self.daily_trades,
            'max_inventory': self.risk_config.get('max_inventory', 10.0),
            'max_volatility': self.risk_config.get('max_volatility', 0.24),
            'margin_buffer': self.risk_config.get('margin_buffer', 2.0)
        } 