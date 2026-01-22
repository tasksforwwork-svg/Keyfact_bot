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
def rewrite_fact(raw):
    prompt = f"""
Ты редактор ЧГК-паблика Cool Bingo.

Оформи факт в формате ЧГК-досье.

Структура:
Факт —
Краткое определение
Историко-культурный контекст
Неочевидные детали
Связи с другими областями
Почему это хорошо работает в ЧГК
Ассоциативные якоря

Требования:
— 10–14 предложений
— энциклопедический стиль
— без разговорных слов
— без морали

Исходный факт:
{raw}

Выводи только готовый текст.
"""

    r = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.55,
    )

    return r.output_text.strip()


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
    text = rewrite_fact(raw)

    await context.bot.send_message(chat_id, text[:4096])

    state["used"].append(raw)
    if mark:
        state["sent"].append(mark)

    save_state(data)


# ---------- команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я присылаю 3 ЧГК-факта в день:\n"
        "🕚 11:00\n🕒 15:00\n🕗 20:00\n\n"
        "Команда /fact — получить факт сразу."
    )


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Факт запрошен. Начинаю обработку…")

    try:
        await update.message.reply_text("1️⃣ Загружаю факты")
        facts = load_facts()
        await update.message.reply_text(f"Фактов найдено: {len(facts)}")

        await update.message.reply_text("2️⃣ Беру случайный факт")
        raw = random.choice(facts)

        await update.message.reply_text("3️⃣ Отправляю в GPT")
        text = rewrite_fact(raw)

        await update.message.reply_text("4️⃣ Готово, отправляю факт")
        await update.message.reply_text(text[:4096])

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка:\n{e}")



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


# ---------- запуск ----------
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    asyncio.create_task(scheduler(app))
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())

