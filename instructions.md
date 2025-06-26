Below is a detailed design document for building a market-making program in Python using the ccxt library for the Hyperliquid exchange, focusing on Solana (SOL) but adaptable to any asset. The program implements a long spot, short perps strategy to collect funding rates while hedging inventory, incorporates funding rate calculations, and uses a volatility measure to adjust spreads dynamically. The architecture follows best coding practices, including modularity, error handling, logging, and configurability.
Design Document: Market-Making Program for Hyperliquid
1. Overview
This program implements a market-making strategy for any asset on the Hyperliquid exchange, with a focus on Solana (SOL). It maintains long spot positions hedged with short perpetual futures (perps) to collect funding rates, aiming to profit from bid-ask spreads while managing inventory and volatility risks. The program uses the ccxt library for exchange interactions, calculates funding rates, and adjusts spreads based on a volatility measure.
Objectives
Place and manage bid-ask quotes on spot markets for liquidity provision.
Hedge spot inventory with short perps to maintain delta-neutral exposure.
Collect funding rate payments from short perps.
Dynamically adjust spreads based on asset volatility.
Ensure robust error handling, logging, and configurability.
Key Features
Asset-Agnostic: Configurable for any Hyperliquid spot/perp pair (e.g., SOL/USDC, BTC/USDC).
Volatility-Adjusted Spreads: Uses Average True Range (ATR) to set spreads.
Funding Rate Integration: Fetches and applies real-time funding rates.
Inventory Management: Caps spot inventory and hedges automatically.
Error Handling: Robust handling of API errors, network issues, and exchange-specific constraints.
Logging: Comprehensive logging for debugging and auditing.
Modular Architecture: Separates concerns (exchange, strategy, risk, logging).
2. Assumptions
Exchange: Hyperliquid, accessed via ccxt (ensure ccxt supports Hyperliquid or use custom API integration if needed).
Asset: Configurable, defaulting to SOL/USDC (spot and perps).
Price: Asset price provided via configuration (e.g., SOL at $143).
Inventory: Configurable, default ±10 SOL (long spot only).
Spread: Target 0.245% (or configurable) for profitability, adjustable based on volatility.
Fees: Spot maker fee 0.0384%, perp maker fee 0.0144%.
Funding Rate: 8% annually (0.0219%/day), fetched real-time if available.
Volatility: 12% daily, measured via ATR (14-period, 1-hour candles).
Hedging: Short perps at 10x leverage.
Trade Volume: 50 round-trip trades/day (configurable).
Runtime: Continuous, with periodic quote updates (e.g., every 5 seconds).
3. Architecture
The program is modular, with components handling specific responsibilities to ensure maintainability and scalability.
Components
Exchange Interface (exchange.py):
Interacts with Hyperliquid via ccxt.
Fetches market data (prices, order book, funding rates).
Places/cancels orders (spot and perps).
Manages account balance and positions.
Market Maker Strategy (strategy.py):
Calculates bid-ask quotes based on mid-price and volatility-adjusted spreads.
Manages inventory and hedging logic.
Incorporates funding rate data for cost calculations.
Volatility Calculator (volatility.py):
Computes ATR (14-period, 1-hour) to measure volatility.
Adjusts spread dynamically based on volatility.
Risk Manager (risk_manager.py):
Enforces inventory limits and leverage constraints.
Implements stop-loss and pause logic for extreme volatility.
Monitors margin to prevent liquidation.
Logger (logger.py):
Logs all actions (quotes, trades, errors, funding rates).
Outputs to console and file for auditing.
Configuration Manager (config.py):
Stores user-defined parameters (asset, inventory size, spread, etc.).
Loads from a JSON file for easy updates.
Main Loop (main.py):
Orchestrates components.
Runs continuous market-making cycle with error handling.
Data Flow
Initialization:
Load config (asset, inventory size, spread, API keys).
Initialize exchange connection and logger.
Market Data Fetch:
Get mid-price, order book, funding rate, and OHLCV data.
Calculate volatility (ATR).
Quote Calculation:
Compute bid (spot) and ask (perp) prices using volatility-adjusted spread.
Order Management:
Place/cancel quotes based on inventory and market conditions.
Hedge spot buys with short perps.
Risk Check:
Monitor inventory, margin, and volatility.
Pause trading if limits are breached.
Logging:
Record all actions, profits, and errors.
4. Best Coding Practices
Modularity: Separate concerns into distinct modules (exchange, strategy, etc.).
Error Handling: Use try-except blocks for API/network errors, with retries and graceful degradation.
Type Hints: Use Python type hints for clarity and IDE support.
Documentation: Include docstrings and comments for all functions/classes.
Configurability: Use JSON config for easy parameter updates.
Logging: Use logging module for debug/info/error levels, with file and console output.
Testing: Include unit tests for critical components (e.g., spread calculation, hedging logic).
Concurrency: Use asyncio for non-blocking API calls and order updates.
Security: Store API keys securely (e.g., environment variables or encrypted config).
Performance: Optimize for low latency (e.g., cache market data, batch API calls).
5. Funding Rate and Volatility Integration
Funding Rate:
Fetch real-time funding rate via ccxt (Hyperliquid’s fetch_funding_rate or equivalent).
Default to 8% annually (0.0219%/day) if API unavailable.
Calculate daily funding income: Funding Income = Inventory × Price × Daily Funding Rate.
Example: For 10 SOL at $143, funding income = 10 × $143 × 0.0219% = $0.31/day.
Volatility:
Use 14-period ATR on 1-hour OHLCV data to measure volatility.
Adjust spread: Spread = Base Spread (0.245%) × (1 + k × ATR / Price), where k is a scaling factor (e.g., 0.5).
Example: If ATR = $17.16 (12% of $143), spread = 0.245% × (1 + 0.5 × 0.12) = 0.2597%.
