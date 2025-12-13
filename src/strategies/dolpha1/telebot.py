import os
import sys
import asyncio
import json
from telegram import Bot


config_path = os.path.join(os.getcwd(), "config_telegram.json")
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)   # config for telegram bot


async def send_tele(msg: str, chat_title: str="alphawave_test"):
    bot = Bot(token=config["bot_token"]["kamp_alphawave_bot"])  # AlphaWaveBot (@kamp_alphawave_bot)
    chat_title = chat_title.replace(" ", "_").lower()
    async with bot:
        await bot.send_message(chat_id=config["chat_id"][chat_title],  # AlphaWave Dolpha1 (Telegram Group chat)
                               text=msg, 
                               parse_mode='Markdown')
