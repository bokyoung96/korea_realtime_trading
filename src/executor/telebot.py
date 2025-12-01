import os
import json
from telegram import Bot


config_path = os.path.join(os.getcwd(), "telegram_config.json")
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)   # config for telegram bot


async def send_tele(msg: str):
    bot = Bot(token=config["bot_token"]["kamp_alphawave_bot"])  # AlphaWaveBot (@kamp_alphawave_bot)
    async with bot:
        await bot.send_message(chat_id=config["chat_id"]["alphawave_dolpha1"],  # AlphaWave Dolpha1 (Telegram Group chat)
                               text=msg, 
                               parse_mode='Markdown')
