import os
import json
import random
import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from openai import OpenAI


# ================== НАСТРОЙКИ ==================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SEND_TIMES = [11, 15, 20]
FACTS_FILE = "facts.txt"
STATE_FILE = "state.json"

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан")

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== ПРОМПТ ==================

COOL_BINGO_PROMPT = """
Ты редактор интеллектуального Telegram-канала в жанре ЧГК и культурной аналитики.

Текст должен выглядеть как публикация канала Cool Bingo.

Структура:

1. Первая строка — чёткое определение: кто или что это, век или годы жизни, краткая характеристика.
2. Краткое описание явления или сюжета без художественности.
3. Исторический и культурный контекст.
4. Несколько возможных версий происхождения или трактовки (если применимо).
5. Связи с другими произведениями, эпохой, наукой или политикой.
6. След в современной культуре или игровой потенциал для ЧГК.

Требования:

— 16–24 предложения
— высокая плотность фактов
— короткие абзацы
— академическая лексика
— без разговорных слов
— без эмодзи
— без списков
— без морали
— допускаются альтернативные гипотезы

Исходный факт:
"""

# ================== СОСТОЯНИЕ ==================

def load_state():
    if not Path(STATE_FILE).exists():
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ================== ФАКТЫ ==================

def load_facts():
    if not Path(FACTS_FILE).exists():
        raise RuntimeError("Файл facts.txt не найден")
    with open(FACTS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# ================== GPT ==================

def rewrite_fact(raw_fact: str) -> str:
    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=COOL_BINGO_PROMPT + raw_fact,
            temperature=0.5,
        )
        return response.output_text.strip()
    except Exception as e:
        return f"Ошибка генерации текста: {e}"

# ================== ОТПРАВКА ==================

async def send_long_message(bot, chat_id, text):
    for i in range(0, len(text), 4096):
        await bot.send_message(chat_id, text[i:i+4096])

# -------- Автоматическая отправка (без повторов) --------

async def send_fact(chat_id: int, context: ContextTypes.DEFAULT_TYPE, mark=None):
    state = load_state()
    today = str(datetime.date.today())

    chat_state = state.setdefault(str(chat_id), {
        "date": today,
        "sent_marks": [],
        "used_facts": []
    })

    if chat_state["date"] != today:
        chat_state["date"] = today
        chat_state["sent_marks"] = []

    if mark and mark in chat_state["sent_marks"]:
        return

    facts = load_facts()
    unused = [f for f in facts if f not in chat_state["used_facts"]]

    if not unused:
        chat_state["used_facts"] = []
        unused = facts

    raw_fact = random.choice(unused)
    text = rewrite_fact(raw_fact)

    await send_long_message(context.bot, chat_id, text)

    chat_state["used_facts"].append(raw_fact)
    if mark:
        chat_state["sent_marks"].append(mark)

    save_state(state)

# -------- Ручная команда /fact (всегда случайный) --------

async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    facts = load_facts()
    raw_fact = random.choice(facts)
    text = rewrite_fact(raw_fact)
    await send_long_message(context.bot, update.effective_chat.id, text)

# -------- Планировщик --------

async def send_scheduled_fact(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await send_fact(job.chat_id, context, mark=job.name)

# ================== КОМАНДА START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    job_queue = context.application.job_queue

    for job in job_queue.jobs():
        if job.chat_id == chat_id:
            job.schedule_removal()

    for hour in SEND_TIMES:
        job_queue.run_daily(
            send_scheduled_fact,
            time=datetime.time(hour, 0),
            name=str(hour),
            chat_id=chat_id,
        )

    await update.message.reply_text(
        "Бот активирован.\n"
        "Автоматическая отправка: 11:00, 15:00, 20:00.\n"
        "Команда /fact — случайный факт."
    )

# ================== ЗАПУСК ==================

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    app.run_polling()

if __name__ == "__main__":
    main()
