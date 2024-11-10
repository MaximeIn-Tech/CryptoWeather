import json
import logging
import os
import socket
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from httpcore import ConnectError
from telegram.ext import Application, CommandHandler

load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(filename)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="logs.log",
    encoding="utf-8",
    filemode="a",
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Initiate the bot token as a variable. The token is stored in a .env file.
token = os.getenv("TOKEN_BOT")

# Initiate the url, it is stored in the env file just for practice
urlCMC = os.getenv("URL_CMC")

# Cache file for the fear and greed data to not make API calls that are not necessary.
FNG_CACHE = {"data": None, "last_update": None}

subscriptions_file = "subscriptions.json"
if not os.path.exists(subscriptions_file):
    with open(subscriptions_file, "w") as file:
        json.dump({"subscribers": []}, file)

# SUPPORT COMMANDS


def is_same_day(date1, date2):
    return date1.date() == date2.date()


def load_subscribers():
    with open(subscriptions_file, "r") as file:
        data = json.load(file)
    return data["subscribers"]


def save_subscribers(subscribers):
    with open(subscriptions_file, "w") as file:
        json.dump({"subscribers": subscribers}, file)


# BOTS COMMANDS


async def start(update, context):
    await update.message.reply_text(
        """
Welcome to the Crypto Weather Bot made by @techsherpa.

This bot is here to help you have access to information about the current crypto market weather.

Available commands are :
- /start to start the bot and get notified twice a day about the change of market.
- /stop to stop receiveing daily updates.
- /update to get an update on the market at any time.
- /halving to get the next halving date.
- /help to get instructions on how to reach me.
"""
    )
    chat_id = update.message.chat_id
    subscribers = load_subscribers()

    if chat_id not in subscribers:
        subscribers.append(chat_id)
        save_subscribers(subscribers)
        await update.message.reply_text(
            "You have been subscribed to updates. You will receive updates at 9AM and 5PM ETC."
        )
    else:
        await update.message.reply_text("You are already subscribed.")

    if update.message.chat.type in ["group", "supergroup"]:
        await context.bot.delete_message(
            chat_id=update.message.chat_id, message_id=update.message.message_id
        )


async def stop(update, context):
    chat_id = update.message.chat_id
    subscribers = load_subscribers()

    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        await update.message.reply_text(
            "You have been unsubscribed from updates. You will no longer receive updates at 9AM and 5PM ETC."
        )
    else:
        await update.message.reply_text("You are not subscribed.")


async def help(update, context):
    if update.message.chat.type in ["group", "supergroup"]:
        await context.bot.delete_message(
            chat_id=update.message.chat_id, message_id=update.message.message_id
        )

    await update.message.reply_text(
        """
If you want to reach me, you can send me a message @techsherpa.

For information, nothing is logged while using this bot.
Simple 🤓
"""
    )


def get_crypto_data(symbol):
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": os.getenv(
            "X_CMC_PRO_API_KEY"
        ),  # The API KEY is stored in .env file
    }

    parameters = {
        "symbol": symbol,
        "convert": "USD",
    }

    try:
        # Make an HTTP GET request to the CoinMarketCap API
        response = requests.get(url, headers=headers, params=parameters)
        response.raise_for_status()  # Raise an error for bad responses

        # Parse the JSON data
        data = response.json()

        # Extract relevant information
        price_usd = float(f"{data['data'][symbol]['quote']['USD']['price']:.2f}")
        day_change = float(
            f"{data['data'][symbol]['quote']['USD']['percent_change_24h']:.2f}"
        )
        week_change = float(
            f"{data['data'][symbol]['quote']['USD']['percent_change_7d']:.2f}"
        )

        return {
            "price_usd": price_usd,
            "day_change": day_change,
            "week_change": week_change,
        }

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None


def getDataBtc():
    return get_crypto_data("BTC")


def getDataEth():
    return get_crypto_data("ETH")


def getFearAndGreed():
    global FNG_CACHE

    # Check if the cache is present and less than one day old
    if FNG_CACHE["data"] is not None and is_same_day(
        FNG_CACHE["last_update"], datetime.now(timezone.utc)
    ):
        print("Fear and Greed Index data fetched from cache.")
        return FNG_CACHE["data"]

    api_url = "https://api.alternative.me/fng/"

    try:
        # Make an HTTP GET request to the API endpoint
        response = requests.get(api_url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON data
            data = response.json()

            # Extract values and value classification
            value = data["data"][0]["value"]
            value_classification = data["data"][0]["value_classification"]

            # Update the cache
            FNG_CACHE["data"] = {
                "value": value,
                "value_classification": value_classification,
            }
            FNG_CACHE["last_update"] = datetime.now(timezone.utc)

            print("Fear and Greed Index data fetched from API.")
            return FNG_CACHE["data"]
        else:
            # Print an error message if the request was not successful
            print(f"Error: Unable to fetch data. Status code: {response.status_code}")
            return None
    except Exception as e:
        # Print an error message if an exception occurs
        print(f"Error: {e}")
        return None


# Returns the BTC halving date.
def get_halving():
    url = "https://chain.api.btc.com/v3/block/latest"
    next_halving_height = 1050000

    # Make the API call
    response = requests.get(url)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()

        # Extract the height from the response
        height = data["data"]["height"]

    blocks_to_halving = next_halving_height - height
    mns_to_halving = blocks_to_halving * 10

    days = mns_to_halving // (24 * 60)
    remaining_minutes = mns_to_halving % (24 * 60)
    hours = remaining_minutes // 60
    minutes = remaining_minutes % 60
    seconds = 0

    # Calculate the date and time until the halving
    current_datetime = datetime.now()
    halving_datetime = current_datetime + timedelta(
        days=days, hours=hours, minutes=minutes, seconds=seconds
    )

    formatted_halving_datetime = halving_datetime.strftime("%d %B %Y %H:%M:%S")
    message = f"<i>Calculated On Average Block Generation Time of 10 Minutes</i>\n\n"
    message += f"<b>Time until halving:</b> {days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
    message += f"\n<b>Estimated halving date and time:</b> {formatted_halving_datetime}"

    return message


# Creates the message for the update.
def get_message():
    btcData = getDataBtc()
    ethData = getDataEth()
    fearAndGreed = getFearAndGreed()

    # Access data from the dictionaries
    btc_price_usd = btcData["price_usd"]
    btc_day_change = btcData["day_change"]
    btc_week_change = btcData["week_change"]

    eth_price_usd = ethData["price_usd"]
    eth_day_change = ethData["day_change"]
    eth_week_change = ethData["week_change"]

    # Format the prices with a space as a separator
    btc_price_usd_formatted = "{:,.2f}".format(btc_price_usd).replace(",", " ")
    eth_price_usd_formatted = "{:,.2f}".format(eth_price_usd).replace(",", " ")

    btc_day_change_text = f"{btc_day_change:+.2f}%"
    btc_week_change_text = f"{btc_week_change:+.2f}%"

    eth_day_change_text = f"{eth_day_change:+.2f}%"
    eth_week_change_text = f"{eth_week_change:+.2f}%"

    fngvalue = fearAndGreed["value"]
    fngsentiment = fearAndGreed["value_classification"]

    message = (
        "<b>BTC/USD</b>\n"
        f"Price: ${btc_price_usd_formatted}\n"
        f"24H Change: {sign_and_emoji(btc_day_change_text)}\n"
        f"7D Change: {sign_and_emoji(btc_week_change_text)}\n\n"
        "<b>ETH/USD</b>\n"
        f"Price: ${eth_price_usd_formatted}\n"
        f"24H Change: {sign_and_emoji(eth_day_change_text)}\n"
        f"7D Change: {sign_and_emoji(eth_week_change_text)}\n\n"
        f"<b>Fear and Greed Index</b>\n"
        f"Score: {fngvalue}\n"
        f"Sentiment: {fngsentiment}"
    )

    return message


async def halving(update, context):
    message = get_halving()

    await context.bot.send_message(
        chat_id=update.message.chat_id, text=message, parse_mode="HTML"
    )

    if update.message.chat.type in ["group", "supergroup"]:
        await context.bot.delete_message(
            chat_id=update.message.chat_id, message_id=update.message.message_id
        )


# Send the update message when the user sends the command.
async def updateData(update, context):
    message = get_message()

    await context.bot.send_message(
        chat_id=update.message.chat_id, text=message, parse_mode="HTML"
    )

    if update.message.chat.type in ["group", "supergroup"]:
        await context.bot.delete_message(
            chat_id=update.message.chat_id, message_id=update.message.message_id
        )


def sign_and_emoji(change_text):
    change = float(change_text[:-1])  # Remove the '%' sign and convert to float
    if change > 0:
        return f"📈 {change_text}"  # Positive change (green arrow up)
    elif change < 0:
        return f"📉 {change_text}"  # Negative change (red arrow down)
    else:
        return f"➡️ {change_text}"  # No change (right arrow)


def main():
    print("Starting bot ...")
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("halving", halving))
    application.add_handler(CommandHandler("update", updateData))
    application.add_handler(CommandHandler("help", help))

    try:
        print("Start polling ...")
        application.run_polling()
    except ConnectError as e:
        logging.error(f"Error while getting Updates: {e}")
    except socket.gaierror as e:
        logging.error(f"Error resolving hostname: {e}")


if __name__ == "__main__":
    main()
