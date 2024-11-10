from main import *
import os
import logging
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Define your token here
token = os.getenv("TOKEN_BOT")

# Initialize the Telegram Bot
bot = Bot(token=token)


async def send_messages():
    message = get_message()
    subscribers = load_subscribers()
    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML",
                disable_notification=True,
            )
        except Exception as e:
            logging.error(f"Error sending message to chat {chat_id}: {e}")


if __name__ == "__main__":
    asyncio.run(send_messages())

# Users on 29th of November : 6269998887, 943254778, 1094356458, 531109953, 534677324, 5158640640, 649771447, 225553086, 449690711, 1246800592, 209634856, 534708508, 498160307, 6033343847, 589450734, 1477038365, 961443156, 338484457, 1193721681, 6351871208, 1454674587, 1084396370, 5312743917, 457936173, 1171127743, 1977622438, 5391941723, 49256656, 472493427, 106484207, 383340451, 500708129, 487410899,
