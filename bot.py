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

# расписание (локальное время сервера)
SCHEDULE_TIMES = ["11:00", "15:00", "20:00"]
# =============================================

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- состояние ----------
def load_state():
    today = str(datetime.date.today())

    if not os.path.exists(STATE_FILE):
        return {
            "date": today,
            "sent": [],
            "used": [],
            "chats": []
        }

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("date") != today:
        data["date"] = today
        data["sent"] = []

    return data


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- загрузка фактов ----------
def load_facts():
    df = pd.read_excel(FACTS_FILE)
    return [
        str(x).strip()
        for x in df.iloc[:, 0]
        if isinstance(x, str) and x.strip()
    ]


# ---------- GPT-редактор (Cool Bingo) ----------
def rewrite_fact(raw_fact: str) -> str:
    prompt = f"""
Ты редактор паблика Cool Bingo (ЧГК).

Перепиши факт в формате ЧГК-досье.

СТРОГО СОБЛЮДАЙ СТРУКТУРУ И АБЗАЦЫ:

Факт — <название>

Краткое определение.
(1–2 предложения, что это вообще такое)

Исторический / культурный контекст.
(когда, где, почему важно)

Неочевидные детали.
(парадоксы, скрытые смыслы, неожиданные факты)

Связи с другими областями.
(литература, кино, философия, наука, политика)

Почему это хорошо работает в ЧГК.
(чем удобно маскируется, на что наводит)

Ассоциативные якоря.
(слова и образы, которыми его «прячут» в вопросах)

ТРЕБОВАНИЯ:
— 10–14 предложений
— энциклопедический, плотный стиль
— без разговорных слов
— без морали и оценок
— обязательные пустые строки между абзацами

ИСХОДНЫЙ ФАКТ:
{raw_fact}

Выводи ТОЛЬКО готовый текст.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.5,
    )

    return response.output_text.strip()


# ---------- отправка факта ----------
async def send_fact(app, chat_id, mark=None):
    state = load_state()
    facts = load_facts()

    unused = [f for f in facts if f not in state["used"]]
    if not unused:
        await app.bot.send_message(chat_id, "Факты закончились.")
        return

    raw = random.choice(unused)
    text = rewrite_fact(raw)

    await app.bot.send_message(chat_id, text[:4096])

    state["used"].append(raw)
    if mark:
        state["sent"].append(mark)

    save_state(state)


# ---------- команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = load_state()

    if chat_id not in state["chats"]:
        state["chats"].append(chat_id)
        save_state(state)

    await update.message.reply_text(
        "Я присылаю 3 ЧГК-факта в день:\n"
        "🕚 11:00\n"
        "🕒 15:00\n"
        "🕗 20:00\n\n"
        "Команда /fact — получить факт сразу."
    )


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await send_fact(context.application, chat_id)


# ---------- планировщик ----------
async def scheduler(app):
    while True:
        now = datetime.datetime.now().strftime("%H:%M")
        state = load_state()

        if now in SCHEDULE_TIMES and now not in state["sent"]:
            for chat_id in state["chats"]:
                await send_fact(app, chat_id, mark=now)

        await asyncio.sleep(60)


# ---------- запуск ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    async def on_startup(app):
        asyncio.create_task(scheduler(app))

    app.post_init = on_startup
    app.run_polling()


if __name__ == "__main__":
    main()
