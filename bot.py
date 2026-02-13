import os
import random
import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from openai import OpenAI


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FACTS_FILE = "facts.txt"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан")

client = OpenAI(api_key=OPENAI_API_KEY)


PROMPT = """
Ты редактор интеллектуального Telegram-канала в жанре ЧГК и культурной аналитики.

Напиши текст в стиле Cool Bingo.
16–22 предложения.
Короткие абзацы.
Без списков.
Без эмодзи.
Без разговорных слов.

Исходный факт:
"""


def load_facts():
    if not Path(FACTS_FILE).exists():
        raise RuntimeError("facts.txt не найден")
    with open(FACTS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def rewrite_fact(raw_fact: str) -> str:
    response = client.responses.create(
        model="gpt-4o-mini",
        input=PROMPT + raw_fact,
        temperature=0.5,
    )
    return response.output_text.strip()


async def send_long_message(bot, chat_id, text):
    for i in range(0, len(text), 4096):
        await bot.send_message(chat_id, text[i:i+4096])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот работает.\nКоманда /fact — случайный факт."
    )


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = load_facts()
    raw_fact = random.choice(facts)

    await update.message.reply_text("Генерирую...")

    text = rewrite_fact(raw_fact)
    await send_long_message(context.bot, update.effective_chat.id, text)


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    print("Бот запущен")

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
