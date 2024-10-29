import ccxt
import time
import threading
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify
import os
import logging

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
TIME_INTERVAL = '1m'
SLEEP_INTERVAL = 60
SELL_PROFIT_MARGIN = 1.05

# Bot state
bought_prices = {}
bot_active = False
bot_thread = None
lock = threading.Lock()  # To handle thread safety

# Helper function to handle errors and log them
def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")  # Fixed here
            return None
    return wrapper

@handle_errors
def fetch_data(pair, data_type="ticker", period=20):
    if data_type == "ohlcv":
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=TIME_INTERVAL, limit=period)
        return [candle[4] for candle in ohlcv]
    elif data_type == "ticker":
        ticker = exchange.fetch_ticker(pair)
        return ticker['last']
    elif data_type == "balance":
        balance = exchange.fetch_balance()
        return balance['total'].get('USDT', 0)

def get_moving_average(pair, period=20):
    close_prices = fetch_data(pair, "ohlcv", period)
    return sum(close_prices) / len(close_prices) if close_prices else None

@handle_errors
def place_order(pair, amount, side="buy"):
    with lock:
        price = fetch_data(pair)
        if price is None:
            logger.error(f"Failed to fetch price for {pair}. Cannot place order.")
            return None

        if side == "buy":
            order = exchange.create_market_buy_order(pair, amount / price)
            logger.info(f"Bought {amount / price} {pair} at price {price}")
            bought_prices[pair] = price
        else:
            order = exchange.create_market_sell_order(pair, amount)
            logger.info(f"Sold {amount} {pair} at price {price}")
            bought_prices.pop(pair, None)
        return order

def monitor_and_trade():
    global bot_active
    baseline_prices = {pair: get_moving_average(pair) for pair in TARGET_PAIRS}
    usdt_per_pair = INVESTMENT / len(TARGET_PAIRS)

    logger.info(f"Initial baseline prices: {baseline_prices}")

    while bot_active:
        for pair in TARGET_PAIRS:
            current_price = fetch_data(pair)
            if current_price is None:
                continue

            target_buy_price = baseline_prices[pair] * (1 - THRESHOLD_PERCENT / 100)
            if current_price <= target_buy_price:
                logger.info(f"{pair} price dropped below {THRESHOLD_PERCENT}% of average. Buying...")
                place_order(pair, usdt_per_pair, "buy")
                baseline_prices[pair] = get_moving_average(pair)

            if pair in bought_prices:
                target_sell_price = bought_prices[pair] * SELL_PROFIT_MARGIN
                balance = fetch_data(pair, "balance")
                if current_price >= target_sell_price and balance > 0:
                    logger.info(f"{pair} price reached target sell price. Selling...")
                    place_order(pair, balance, "sell")

        time.sleep(SLEEP_INTERVAL)

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the trading bot API!"}), 200

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/start', methods=['GET'])
def start_bot():
    global bot_active, bot_thread
    if not bot_active:
        bot_active = True
        bot_thread = threading.Thread(target=monitor_and_trade)
        bot_thread.start()
        return jsonify({"status": "Bot started"}), 200
    else:
        return jsonify({"status": "Bot is already running"}), 400

@app.route('/stop', methods=['GET'])
def stop_bot():
    global bot_active, bot_thread
    if bot_active:
        bot_active = False
        bot_thread.join()
        return jsonify({"status": "Bot stopped"}), 200
    else:
        return jsonify({"status": "Bot is not running"}), 400

@app.route('/status', methods=['GET'])
def status():
    with lock:
        return jsonify({
            "bot_active": bot_active,
            "bought_prices": bought_prices
        }), 200

if __name__ == '__main__':  # Fixed here
    app.run(host='0.0.0.0', port=8080, debug=True)  # Change port as needed
