import asyncio
import json
import logging
import os
import ssl
import time
from datetime import datetime, timedelta

import websocket
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

from main import load_subscribers

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Telegram Bot
token = os.getenv("TOKEN_BOT")
bot = Bot(token=token)

# Constants
COOLDOWN_PERIOD = 10  # In seconds
PERCENTAGE_THRESHOLD = 0.1  # 0.1% increase for new ATH notification
TWAP_WINDOW = 20  # In seconds
MAX_NOTIFICATIONS_PER_HOUR = 3

# Global variables
ath_values = {}
last_notification_time = {"BTCUSDT": datetime.min, "ETHUSDT": datetime.min}
price_history = {"BTCUSDT": [], "ETHUSDT": []}
notification_count = {"BTCUSDT": 0, "ETHUSDT": 0}
notification_reset_time = {"BTCUSDT": datetime.now(), "ETHUSDT": datetime.now()}


def load_ath_values():
    try:
        with open("ath_values.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"BTCUSDT": 0, "ETHUSDT": 0}


def save_ath_values(ath_values):
    with open("ath_values.json", "w") as file:
        json.dump(ath_values, file)


ath_values = load_ath_values()


async def broadcast_to_users(message):
    subscribers = load_subscribers()
    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML",
                disable_notification=True,
            )
        except TelegramError as e:
            logger.error(f"Error sending message to chat {chat_id}: {e}")


def calculate_twap(symbol):
    if len(price_history[symbol]) == 0:
        return None
    return sum(price for price, _ in price_history[symbol]) / len(price_history[symbol])


def update_price_history(symbol, price):
    current_time = datetime.now()
    price_history[symbol].append((price, current_time))
    price_history[symbol] = [
        (p, t)
        for p, t in price_history[symbol]
        if current_time - t <= timedelta(seconds=TWAP_WINDOW)
    ]


def check_and_update_ath(symbol, current_price):
    global ath_values, last_notification_time, notification_count, notification_reset_time

    current_time = datetime.now()
    twap = calculate_twap(symbol)

    if twap is None:
        return

    if twap > ath_values.get(symbol, 0) * (1 + PERCENTAGE_THRESHOLD / 100):
        if (
            current_time - last_notification_time[symbol]
        ).total_seconds() > COOLDOWN_PERIOD:
            if current_time - notification_reset_time[symbol] > timedelta(hours=1):
                notification_count[symbol] = 0
                notification_reset_time[symbol] = current_time

            if notification_count[symbol] < MAX_NOTIFICATIONS_PER_HOUR:
                ath_values[symbol] = twap
                save_ath_values(ath_values)
                logger.info(
                    f"New ATH for {symbol[:-4]} at ${twap:.2f} , sending message"
                )
                asyncio.run(
                    broadcast_to_users(
                        f"🎉 New All-Time High for {symbol[:-4]}: ${twap:.2f}!"
                    )
                )
                last_notification_time[symbol] = current_time
                notification_count[symbol] += 1


def on_message(ws, message):
    data = json.loads(message)
    symbol = data["s"]
    current_price = float(data["p"])
    print(f"Received price for {symbol}: ${current_price}")
    update_price_history(symbol, current_price)
    check_and_update_ath(symbol, current_price)


def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    logger.info(
        f"WebSocket closed with code: {close_status_code}, message: {close_msg}"
    )


def on_open(ws):
    logger.info("WebSocket connection opened")
    # Subscribe to the streams
    subscribe_message = {
        "method": "SUBSCRIBE",
        "params": ["btcusdt@trade", "ethusdt@trade"],
        "id": 1,
    }
    ws.send(json.dumps(subscribe_message))


def start_websocket():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://stream.binance.com:9443/ws",
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False})
        except Exception as e:
            logger.error(f"Exception occurred: {e}")
        time.sleep(60)
        logger.info("Reconnecting to WebSocket...")


if __name__ == "__main__":
    start_websocket()
