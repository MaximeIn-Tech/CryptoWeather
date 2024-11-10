import asyncio
import json
import logging
import os
import ssl
import time

import websocket
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

from main import *

load_dotenv()

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Define your token here
token = os.getenv("TOKEN_BOT")

# Initialize the Telegram Bot
bot = Bot(token=token)


# Load ATH values from JSON file
def load_ath_values():
    with open("ath_values.json", "r") as file:
        return json.load(file)


# Save ATH values to JSON file
def save_ath_values(ath_values):
    with open("ath_values.json", "w") as file:
        json.dump(ath_values, file)


# Load initial ATH values
ath_values = load_ath_values()
BTC_ATH = ath_values.get("BTC")
print(f"BTC ATH is: {BTC_ATH}")
ETH_ATH = ath_values.get("ETH")
print(f"ETH ATH is: {ETH_ATH}")


# Function to broadcast message to all users
async def broadcast_to_users(message):
    subscribers = load_subscribers()
    try:
        await bot.send_message(
            chat_id=1355080202,
            text=message,
            parse_mode="HTML",
            disable_notification=True,
        )
    except TelegramError as e:
        logging.error(f"Error sending message to chat {1355080202}: {e}")


# Function to handle BTC WebSocket messages
def on_message_btc(ws, message):
    global BTC_ATH
    data = json.loads(message)
    if data["s"] == "BTCUSDT":
        current_btc_price = float(data["p"])
        print(f"Current BTC price is: {current_btc_price}")
        if current_btc_price > BTC_ATH:
            BTC_ATH = current_btc_price
            ath_values["BTC"] = BTC_ATH
            save_ath_values(ath_values)
            asyncio.run(
                broadcast_to_users(f"🎉 New All-Time High for BTC: ${BTC_ATH}!")
            )
    time.sleep(10)


# Function to handle ETH WebSocket messages
def on_message_eth(ws, message):
    global ETH_ATH
    data = json.loads(message)
    if data["s"] == "ETHUSDT":
        current_eth_price = float(data["p"])
        print(f"Current ETH price is: {current_eth_price}")
        if current_eth_price > ETH_ATH:
            ETH_ATH = current_eth_price
            ath_values["ETH"] = ETH_ATH
            save_ath_values(ath_values)
            asyncio.run(
                broadcast_to_users(f"🎉 New All-Time High for ETH: ${ETH_ATH}!")
            )
    time.sleep(10)


# Function to handle WebSocket errors
def on_error(ws, error):
    print("WebSocket error:", error)


# Function to handle WebSocket closure
def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed with code:", close_status_code, ", message:", close_msg)


# Function to handle WebSocket opening
def on_open(ws):
    print("WebSocket connection opened")


# Start WebSocket connection with reconnection handling for BTC
def start_btc_websocket():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://stream.binance.com:9443/ws/btcusdt@trade",
                on_message=on_message_btc,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False})
        except Exception as e:
            print("Exception occurred:", e)
        time.sleep(60)
        print("Reconnecting to BTC WebSocket...")


# Start WebSocket connection with reconnection handling for ETH
def start_eth_websocket():
    while True:
        try:
            ws = websocket.WebSocketApp(
                "wss://stream.binance.com:9443/ws/ethusdt@trade",
                on_message=on_message_eth,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False})
        except Exception as e:
            print("Exception occurred:", e)
        time.sleep(60)
        print("Reconnecting to ETH WebSocket...")


# Async function to run both WebSocket connections concurrently
async def run_websockets():
    # Run both WebSocket connections concurrently
    await asyncio.gather(
        asyncio.to_thread(start_btc_websocket), asyncio.to_thread(start_eth_websocket)
    )


# Start monitoring
if __name__ == "__main__":
    asyncio.run(run_websockets())
