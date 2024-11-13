import asyncio
import json
import logging
import os
import ssl
import threading
from datetime import datetime, timedelta

import websocket
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

from main import load_subscribers

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Telegram Bot
token = os.getenv("TOKEN_BOT")

trequest = HTTPXRequest(connection_pool_size=20)
bot = Bot(token=token, request=trequest)

# Constants
COOLDOWN_PERIOD = 10  # In seconds
PERCENTAGE_THRESHOLD = 0.1  # 0.1% increase for new ATH notification
TWAP_WINDOW = 2  # In seconds

# Global variables
ath_values = {}
last_notification_time = {"BTCUSDT": datetime.min, "ETHUSDT": datetime.min}
price_history = {"BTCUSDT": [], "ETHUSDT": []}


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
    try:
        subscribers = load_subscribers()
        for chat_id in subscribers:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="HTML",
                    disable_notification=True,
                )
                await asyncio.sleep(0.1)
            except TelegramError as e:
                logger.error(f"Error sending message to chat {chat_id}: {e}")
    except Exception as e:
        # Log the error or handle it accordingly
        print(f"Error broadcasting to users: {e}")


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


async def check_and_update_ath(symbol, current_price):
    global ath_values, last_notification_time

    current_time = datetime.now()
    twap = calculate_twap(symbol)

    if twap is None:
        return

    if twap > ath_values.get(symbol, 0) * (1 + PERCENTAGE_THRESHOLD / 100):
        if (
            current_time - last_notification_time[symbol]
        ).total_seconds() > COOLDOWN_PERIOD:
            ath_values[symbol] = twap
            save_ath_values(ath_values)
            logger.info(f"New ATH for {symbol[:-4]} at ${twap:.2f} , sending message")
            await broadcast_to_users(
                f"🎉 New All-Time High for {symbol[:-4]}: ${twap:.2f}!"
            )
            last_notification_time[symbol] = current_time


async def handle_websocket_message(message):
    data = json.loads(message)
    symbol = data["s"]
    current_price = float(data["p"])
    print(f"Received price for {symbol}: ${current_price}")
    update_price_history(symbol, current_price)
    await check_and_update_ath(symbol, current_price)


def on_message(ws, message):
    asyncio.run(handle_websocket_message(message))


def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    logger.info(
        f"WebSocket connection closed with code: {close_status_code}, message: {close_msg}"
    )


def on_open(ws):
    logger.info("WebSocket connection opened")
    subscribe_message = {
        "method": "SUBSCRIBE",
        "params": ["btcusdt@trade", "ethusdt@trade"],
        "id": 1,
    }
    ws.send(json.dumps(subscribe_message))


async def websocket_loop():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://stream.binance.com:9443/ws",
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            wst = threading.Thread(
                target=ws.run_forever,
                kwargs={
                    "sslopt": {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
                },
            )
            wst.daemon = True
            wst.start()

            # Keep the main loop running
            while wst.is_alive():
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Exception occurred: {e}")

        logger.info("Reconnecting to WebSocket...")
        await asyncio.sleep(5)


async def main():
    websocket_task = asyncio.create_task(websocket_loop())
    await websocket_task


if __name__ == "__main__":
    asyncio.run(main())
