import os
import json
import random
import datetime
import asyncio
import pandas as pd

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from openai import OpenAI

# ================= НАСТРОЙКИ =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FACTS_FILE = "facts.xlsx"
STATE_FILE = "state.json"

SCHEDULE_HOURS = ["11", "15", "20"]
# =============================================

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------- состояние ----------
def load_state():
    today = str(datetime.date.today())

    if not os.path.exists(STATE_FILE):
        return {}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for chat_id, state in data.items():
        if state.get("date") != today:
            state["date"] = today
            state["sent"] = []

    return data


def save_state(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- факты ----------
def load_facts():
    df = pd.read_excel(FACTS_FILE)
    return [
        str(x).strip()
        for x in df.iloc[:, 0]
        if isinstance(x, str) and x.strip()
    ]


# ---------- GPT-редактор ----------
def rewrite_fact(raw_fact: str) -> str:
    prompt = f"""
Ты редактор ЧГК-паблика Cool Bingo.

Оформи факт в формате ЧГК-досье.

Строгая структура:
Факт —
Краткое определение
Историко-культурный контекст
Неочевидные детали
Связи с другими областями
Почему это хорошо работает в ЧГК
Ассоциативные якоря

Требования:
— 10–14 предложений
— плотный энциклопедический стиль
— без разговорных слов
— без морали и оценок
— текст должен выглядеть как готовый пост

Исходный факт:
{raw_fact}

Выводи только готовый текст.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.55,
    )

    return response.output_text.strip()


# ---------- отправка ----------
async def send_fact(chat_id: int, app, mark: str | None = None):
    data = load_state()

    if str(chat_id) not in data:
        data[str(chat_id)] = {
            "date": str(datetime.date.today()),
            "sent": [],
            "used": [],
        }

    state = data[str(chat_id)]
    facts = load_facts()

    unused = [f for f in facts if f not in state["used"]]
    if not unused:
        await app.bot.send_message(chat_id, "Факты закончились.")
        return

    raw = random.choice(unused)

    # GPT — в отдельном потоке, чтобы не блокировать event loop
    text = await asyncio.to_thread(rewrite_fact, raw)

    await app.bot.send_message(chat_id, text[:4096])

    state["used"].append(raw)
    if mark:
        state["sent"].append(mark)

    save_state(data)


# ---------- команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я присылаю 3 ЧГК-факта в день:\n"
        "🕚 11:00\n"
        "🕒 15:00\n"
        "🕗 20:00\n\n"
        "Команда /fact — получить факт сразу."
    )

    chat_id = update.effective_chat.id
    data = load_state()
    if str(chat_id) not in data:
        data[str(chat_id)] = {
            "date": str(datetime.date.today()),
            "sent": [],
            "used": [],
        }
        save_state(data)


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Готовлю факт…")
    await send_fact(chat_id, context.application)


# ---------- планировщик ----------
async def scheduler(app):
    while True:
        now = datetime.datetime.now()
        hour = now.strftime("%H")

        data = load_state()

        for chat_id, state in data.items():
            if hour in SCHEDULE_HOURS and hour not in state["sent"]:
                await send_fact(int(chat_id), app, mark=hour)

        await asyncio.sleep(60)


# ---------- запуск ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    app.job_queue.run_once(lambda *_: asyncio.create_task(scheduler(app)), 1)

    app.run_polling()


if __name__ == "__main__":
    main()
