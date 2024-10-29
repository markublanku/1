import ccxt
import time
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Set up exchange (Binance in this case) using environment variables
exchange = ccxt.binance({
    'apiKey': os.getenv('API_KEY'),
    'secret': os.getenv('SECRET_KEY'),
    'enableRateLimit': True
})

# Configuration
TARGET_PAIRS = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "DOGE/USDT", "PEPE/USDT", "SHIB/USDT", "SUI/USDT", "NEIRO/USDT", "CYBER/USDT"]
INVESTMENT = 85  # total investment in USDT
THRESHOLD_PERCENT = 5
TIME_INTERVAL = '1m'  # e.g., '1m', '5m', '1h', etc.
SLEEP_INTERVAL = 60  # seconds between each loop cycle
SELL_PROFIT_MARGIN = 1.05  # 5% above buy price

# Dictionary to track buying prices for each pair
bought_prices = {}

# Error-handling decorator
def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return None
    return wrapper

# Helper function to fetch data
@handle_errors
def fetch_data(pair, data_type="ticker", period=20):
    if data_type == "ohlcv":
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=TIME_INTERVAL, limit=period)
        return [candle[4] for candle in ohlcv]  # Get closing prices
    elif data_type == "ticker":
        ticker = exchange.fetch_ticker(pair)
        return ticker['last']
    elif data_type == "balance":
        balance = exchange.fetch_balance()
        return balance['total'].get(pair.split('/')[0], 0)

# Helper function to get moving average
def get_moving_average(pair, period=20):
    close_prices = fetch_data(pair, "ohlcv", period)
    return sum(close_prices) / len(close_prices) if close_prices else None

# Buy and sell functions
@handle_errors
def place_order(pair, amount, side="buy"):
    if side == "buy":
        price = fetch_data(pair)
        order = exchange.create_market_buy_order(pair, amount / price)
        print(f"{datetime.now()}: Bought {amount / price} {pair} at price {price}")
        bought_prices[pair] = price
    else:
        price = fetch_data(pair)
        order = exchange.create_market_sell_order(pair, amount)
        print(f"{datetime.now()}: Sold {amount} {pair} at price {price}")
        bought_prices.pop(pair, None)  # Remove after selling
    return order

# Main function to monitor prices and trade
def monitor_and_trade():
    baseline_prices = {pair: get_moving_average(pair) for pair in TARGET_PAIRS}
    usdt_per_pair = INVESTMENT / len(TARGET_PAIRS)  # Split investment per pair

    print(f"Initial baseline prices: {baseline_prices}")

    while True:
        for pair in TARGET_PAIRS:
            current_price = fetch_data(pair)
            if current_price is None:
                continue  # Skip if price fetch fails

            # Buy logic
            target_buy_price = baseline_prices[pair] * (1 - THRESHOLD_PERCENT / 100)
            if current_price <= target_buy_price:
                print(f"{pair} price dropped below {THRESHOLD_PERCENT}% of the average price. Buying...")
                place_order(pair, usdt_per_pair, "buy")
                baseline_prices[pair] = get_moving_average(pair)  # Update baseline

            # Sell logic
            if pair in bought_prices:
                target_sell_price = bought_prices[pair] * SELL_PROFIT_MARGIN
                balance = fetch_data(pair, "balance")
                if current_price >= target_sell_price and balance > 0:
                    print(f"{pair} price reached target sell price. Selling...")
                    place_order(pair, balance, "sell")

        time.sleep(SLEEP_INTERVAL)  # Pause before the next check

# Run the bot
monitor_and_trade()
