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

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не задан")

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- состояние ----------
def load_state(chat_id):
    today = str(datetime.date.today())

    if not os.path.exists(STATE_FILE):
        return {str(chat_id): {"date": today, "sent": [], "used": []}}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if str(chat_id) not in data:
        data[str(chat_id)] = {"date": today, "sent": [], "used": []}

    if data[str(chat_id)]["date"] != today:
        data[str(chat_id)]["date"] = today
        data[str(chat_id)]["sent"] = []

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
async def rewrite_fact(raw):
    prompt = f"""
Ты редактор ЧГК-паблика Cool Bingo.

Оформи факт в формате ЧГК-досье.

Структура:
Факт —
Краткое определение.
Историко-культурный контекст.
Неочевидные детали и скрытые смыслы.
Связи с другими областями знания.
Почему этот факт хорошо работает в ЧГК.
Ассоциативные якоря (ложные ходы, маскировка).

Требования:
— 10–14 предложений
— энциклопедический стиль
— без разговорных слов
— без морали
— без вопросов

Исходный факт:
{raw}

Выводи только готовый текст.
"""

    response = await asyncio.to_thread(
        client.responses.create,
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.55,
    )

    return response.output_text.strip()


# ---------- отправка ----------
async def send_fact_to_chat(chat_id, context, mark=None):
    data = load_state(chat_id)
    state = data[str(chat_id)]

    facts = load_facts()
    unused = [f for f in facts if f not in state["used"]]

    if not unused:
        await context.bot.send_message(chat_id, "Факты закончились.")
        return

    raw = random.choice(unused)
    text = await rewrite_fact(raw)

    await context.bot.send_message(chat_id, text[:4096])

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


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("Подбираю факт…")
        await send_fact_to_chat(update.effective_chat.id, context)
    except Exception as e:
        await update.message.reply_text(f"Ошибка:\n{e}")


# ---------- расписание ----------
async def scheduler(app):
    while True:
        now = datetime.datetime.now()
        hour = now.strftime("%H")

        if not os.path.exists(STATE_FILE):
            await asyncio.sleep(60)
            continue

        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for chat_id, state in data.items():
            if hour in SCHEDULE_HOURS and hour not in state["sent"]:
                await send_fact_to_chat(int(chat_id), app.bot, mark=hour)

        await asyncio.sleep(60)


async def on_startup(app):
    asyncio.create_task(scheduler(app))


# ---------- запуск ----------
async def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
