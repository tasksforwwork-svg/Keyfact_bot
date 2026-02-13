import os
import random
from pathlib import Path
import pandas as pd
import requests

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


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
Стиль энциклопедический, плотный, без разговорной лексики.
Абзацы короткие.
"""

USER_PROMPT_TEMPLATE = """
Оформи материал в стиле Cool Bingo.

Первая строка — чёткое определение (что это, годы, краткая характеристика).

Далее 5–7 коротких абзацев.

Обязательно:
— исторический контекст
— малоизвестные детали
— альтернативные версии или трактовки
— культурные или научные связи
— объяснение, почему тема удобна для ЧГК

Требования:
— минимум 20 предложений
— высокая плотность фактов
— без списков
— без эмодзи
— без морали

Факт: {fact}
"""


# ================= ЗАГРУЗКА ФАКТОВ =================

def load_facts():
    if not Path(FACTS_FILE).exists():
        raise RuntimeError("facts.xlsx не найден")

    df = pd.read_excel(FACTS_FILE)

    facts = [
        str(x).strip()
        for x in df.iloc[:, 0]
        if isinstance(x, str) and x.strip()
    ]

    if not facts:
        raise RuntimeError("В Excel нет фактов")

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
                    "model": "google/gemma-2-9b-it:free",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(fact=raw_fact)}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1800
                },
                timeout=120,
            )

            data = response.json()

            if "choices" in data:
                text = data["choices"][0]["message"]["content"].strip()

                if len(text) > 800:
                    return text

            return "Модель вернула слишком короткий ответ. Попробуйте ещё раз."

        except requests.exceptions.RequestException:
            if attempt == 2:
                return "Сервер модели временно недоступен. Попробуйте позже."


# ================= TELEGRAM =================

async def send_long_message(bot, chat_id, text):
    for i in range(0, len(text), 4096):
        await bot.send_message(chat_id, text[i:i+4096])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот запущен.\nКоманда /fact — получить случайный факт."
    )


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        facts = load_facts()
        raw_fact = random.choice(facts)

        await update.message.reply_text("Генерирую...")

        text = rewrite_fact(raw_fact)
        await send_long_message(context.bot, update.effective_chat.id, text)

    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


# ================= ЗАПУСК =================

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("fact", manual_fact))

print("Бот запущен")

app.run_polling()
