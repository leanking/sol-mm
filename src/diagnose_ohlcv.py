import sys
import os

# No need to modify sys.path when running as a module

from config import ConfigManager
from logger import MarketMakerLogger
from exchange import HyperliquidExchange

if __name__ == "__main__":
    config = ConfigManager()
    logger = MarketMakerLogger()
    exchange = HyperliquidExchange(config, logger)

    if not exchange.connect():
        print("❌ Failed to connect to exchange.")
        sys.exit(1)

    spot_symbol = 'USOL/USDC'
    perp_symbol = 'SOL/USDC:USDC'
    timeframe = '1h'
    limit = 15

    print(f"\nTesting OHLCV and ticker for spot: {spot_symbol}")
    try:
        ohlcv = exchange.exchange.fetch_ohlcv(spot_symbol, timeframe, limit=limit)
        print(f"OHLCV ({spot_symbol}, {timeframe}, {limit}): {ohlcv if ohlcv else 'No data'}")
    except Exception as e:
        print(f"❌ Error fetching OHLCV for {spot_symbol}: {e}")
    try:
        ticker = exchange.exchange.fetch_ticker(spot_symbol)
        print(f"Ticker ({spot_symbol}): {ticker}")
    except Exception as e:
        print(f"❌ Error fetching ticker for {spot_symbol}: {e}")

    print(f"\nTesting OHLCV and ticker for perp: {perp_symbol}")
    try:
        ohlcv = exchange.exchange.fetch_ohlcv(perp_symbol, timeframe, limit=limit)
        print(f"OHLCV ({perp_symbol}, {timeframe}, {limit}): {ohlcv if ohlcv else 'No data'}")
    except Exception as e:
        print(f"❌ Error fetching OHLCV for {perp_symbol}: {e}")
    try:
        ticker = exchange.exchange.fetch_ticker(perp_symbol)
        print(f"Ticker ({perp_symbol}): {ticker}")
    except Exception as e:
        print(f"❌ Error fetching ticker for {perp_symbol}: {e}") 