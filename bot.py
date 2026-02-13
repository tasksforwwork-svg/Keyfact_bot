import os
import random
from pathlib import Path
import pandas as pd
import requests
from datetime import time

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ================= НАСТРОЙКИ =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

FACTS_FILE = "facts.xlsx"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан")

if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY не задан")


# ================= ПРОМПТ =================

SYSTEM_PROMPT = """
Ты редактор интеллектуального Telegram-канала Cool Bingo.
Пишешь строго на русском языке.
Стиль плотный, аналитический, энциклопедический.
Абзацы короткие.
Без разговорной лексики.
"""

USER_PROMPT_TEMPLATE = """
Оформи материал в стиле Cool Bingo.

Первая строка — чёткое определение.

Далее 5–7 коротких абзацев.

Обязательно:
— исторический контекст
— малоизвестные детали
— альтернативные трактовки
— культурные или научные связи
— потенциал для ЧГК

Минимум 18 предложений.
Без списков.
Без эмодзи.
Без морали.

Факт: {fact}
"""


# ================= ФАКТЫ =================

def load_facts():
    if not Path(FACTS_FILE).exists():
        raise RuntimeError("facts.xlsx не найден")

    df = pd.read_excel(FACTS_FILE)

    facts = [
        str(x).strip()
        for x in df.iloc[:, 0]
        if isinstance(x, str) and x.strip()
    ]

    return facts


# ================= ГЕНЕРАЦИЯ =================

def rewrite_fact(raw_fact: str):

    for attempt in range(3):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openrouter/auto",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(fact=raw_fact)}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500
                },
                timeout=90,
            )

            data = response.json()

            if "choices" in data:
                text = data["choices"][0]["message"]["content"].strip()

                if len(text) > 700:
                    return text

            return "Модель вернула короткий ответ. Попробуйте ещё раз."

        except requests.exceptions.RequestException:
            if attempt == 2:
                return "Модель временно недоступна. Попробуйте позже."


async def send_long_message(bot, chat_id, text):
    for i in range(0, len(text), 4096):
        await bot.send_message(chat_id, text[i:i+4096])


# ================= ПРИВЕТСТВИЕ =================

WELCOME_TEXT = (
    "Cool Bingo\n\n"
    "Здесь публикуются факты, которые выглядят безобидно.\n"
    "Пока не становятся вопросом.\n\n"
    "Материалы оформлены как культурные мини-досье: "
    "контекст возникновения, малоизвестные детали, версии и пересечения с другими областями знания.\n\n"
    "Команды:\n"
    "/fact — получить факт\n"
    "/help — вспомнить правила игры\n\n"
    "Автоматические публикации:\n"
    "11:00\n"
    "12:45\n"
    "17:45\n\n"
    "Дополнительный факт можно запросить в любой момент.\n"
    "Подготовка никогда не бывает избыточной."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [["Получить факт"]]

    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )
    )

    schedule_jobs(update.effective_chat.id, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT)


# ================= РАСПИСАНИЕ =================

def schedule_jobs(chat_id, context):

    job_queue = context.application.job_queue

    times = [
        time(11, 0),
        time(12, 45),
        time(17, 45),
    ]

    for t in times:
        job_queue.run_daily(
            send_scheduled_fact,
            time=t,
            chat_id=chat_id,
            name=f"{chat_id}_{t}"
        )


async def send_scheduled_fact(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    facts = load_facts()
    raw_fact = random.choice(facts)
    text = rewrite_fact(raw_fact)
    await send_long_message(context.bot, chat_id, text)


# ================= РУЧНОЙ ФАКТ =================

async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = load_facts()
    raw_fact = random.choice(facts)
    await update.message.reply_text("Генерирую...")
    text = rewrite_fact(raw_fact)
    await send_long_message(context.bot, update.effective_chat.id, text)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Получить факт":
        await manual_fact(update, context)


# ================= ЗАПУСК =================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("fact", manual_fact))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

print("Бот запущен")

app.run_polling()
