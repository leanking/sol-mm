#!/usr/bin/env python3
"""
Test script to verify Hyperliquid market discovery and API wallet configuration.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import using absolute imports
from .config import ConfigManager
from .logger import MarketMakerLogger
from .exchange import HyperliquidExchange

def test_market_discovery():
    """Test market discovery functionality."""
    print("Testing Hyperliquid market discovery...")
    
    try:
        # Initialize components
        config = ConfigManager()
        logger = MarketMakerLogger()
        exchange = HyperliquidExchange(config, logger)
        
        # Test connection
        print("Connecting to Hyperliquid...")
        if not exchange.connect():
            print("❌ Failed to connect to Hyperliquid")
            return False
        
        print("✅ Successfully connected to Hyperliquid")
        
        # Test market discovery
        print("\nDiscovering SOL markets...")
        spot_symbol, perp_symbol = exchange.find_solana_markets()
        
        if spot_symbol:
            print(f"✅ Found SOL spot market: {spot_symbol}")
        else:
            print("❌ No SOL spot market found")
        
        if perp_symbol:
            print(f"✅ Found SOL perpetual market: {perp_symbol}")
        else:
            print("❌ No SOL perpetual market found")
        
        # Test market info
        if spot_symbol:
            print(f"\nTesting spot market info for {spot_symbol}...")
            spot_info = exchange.get_market_info(spot_symbol)
            if spot_info:
                print(f"✅ Spot market info: {spot_info.get('type', 'unknown')} market")
            else:
                print("❌ Failed to get spot market info")
        
        if perp_symbol:
            print(f"\nTesting perpetual market info for {perp_symbol}...")
            perp_info = exchange.get_market_info(perp_symbol)
            if perp_info:
                print(f"✅ Perpetual market info: {perp_info.get('type', 'unknown')} market")
            else:
                print("❌ Failed to get perpetual market info")
        
        # Test balance fetch
        print("\nTesting balance fetch...")
        balance = exchange.get_balance()
        if balance:
            print("✅ Successfully fetched balance")
            # Show available currencies
            currencies = [curr for curr, bal in balance.items() if bal.get('free', 0) > 0 or bal.get('total', 0) > 0]
            if currencies:
                print(f"Available currencies: {currencies}")
        else:
            print("❌ Failed to fetch balance")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

def test_environment_variables():
    """Test environment variable configuration."""
    print("Testing environment variables...")
    
    try:
        config = ConfigManager()
        exchange_config = config.get_exchange_config()
        
        api_wallet = exchange_config.get('api_wallet')
        api_wallet_private = exchange_config.get('api_wallet_private')
        main_wallet = exchange_config.get('main_wallet')
        
        if api_wallet:
            print(f"✅ API Wallet: {api_wallet[:10]}...{api_wallet[-10:]}")
        else:
            print("❌ API Wallet not found")
        
        if api_wallet_private:
            print(f"✅ API Wallet Private: {api_wallet_private[:10]}...{api_wallet_private[-10:]}")
        else:
            print("❌ API Wallet Private not found")
        
        if main_wallet:
            print(f"✅ Main Wallet: {main_wallet[:10]}...{main_wallet[-10:]}")
        else:
            print("❌ Main Wallet not found")
        
        return all([api_wallet, api_wallet_private, main_wallet])
        
    except Exception as e:
        print(f"❌ Error testing environment variables: {e}")
        return False

if __name__ == "__main__":
    print("Hyperliquid Market Discovery Test")
    print("=" * 40)
    
    # Test environment variables first
    env_ok = test_environment_variables()
    print()
    
    if env_ok:
        # Test market discovery
        market_ok = test_market_discovery()
        
        if market_ok:
            print("\n🎉 All tests passed! The bot should be ready to run.")
        else:
            print("\n❌ Market discovery tests failed. Check your configuration.")
    else:
        print("\n❌ Environment variable tests failed. Check your .env file.") 