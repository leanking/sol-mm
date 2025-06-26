import json
import os
from typing import Dict, Any
from dotenv import load_dotenv

class ConfigManager:
    """Manages configuration for the market making program."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to the JSON configuration file
        """
        load_dotenv()  # Load environment variables from .env file
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file and environment variables."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Add environment variables to config using Hyperliquid's API wallet terminology
            config['exchange']['api_wallet'] = os.getenv('HYPERLIQUID_API_WALLET')
            config['exchange']['api_wallet_private'] = os.getenv('HYPERLIQUID_API_WALLET_PRIVATE')
            config['exchange']['main_wallet'] = os.getenv('HYPERLIQUID_MAIN_WALLET')
            
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {self.config_path} not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_exchange_config(self) -> Dict[str, Any]:
        """Get exchange configuration."""
        return self.config.get('exchange', {})
    
    def get_asset_config(self) -> Dict[str, Any]:
        """Get asset configuration."""
        return self.config.get('asset', {})
    
    def get_fees_config(self) -> Dict[str, Any]:
        """Get fees configuration."""
        return self.config.get('fees', {})
    
    def get_volatility_config(self) -> Dict[str, Any]:
        """Get volatility configuration."""
        return self.config.get('volatility', {})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """Get risk configuration."""
        return self.config.get('risk', {})
    
    def get_trading_config(self) -> Dict[str, Any]:
        """Get trading configuration."""
        return self.config.get('trading', {}) 