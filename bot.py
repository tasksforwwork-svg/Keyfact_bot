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

SCHEDULE_TIMES = ["11:00", "15:00", "20:00"]
# =============================================

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------- состояние ----------
def load_state():
    today = str(datetime.date.today())

    if not os.path.exists(STATE_FILE):
        return {"date": today, "sent": [], "used": []}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if state.get("date") != today:
        state["date"] = today
        state["sent"] = []

    return state


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
Ты — редактор интеллектуального ЧГК-паблика в стиле Cool Bingo.

Твоя задача — превратить исходный факт в ЧГК-досье.
Это НЕ пересказ, НЕ биография и НЕ энциклопедическая статья.

ОБЩИЕ ТРЕБОВАНИЯ:
— 10–14 предложений
— строгий, спокойный, интеллектуальный тон
— без разговорной речи
— без морализаторства
— без оценочных эпитетов
— обязательное деление на абзацы

СТРУКТУРА (ОБЯЗАТЕЛЬНА):

1. Факт — краткое определение объекта.
2. Исторический или культурный контекст.
3. Ключевая идея или парадокс.
4. Связи с другими областями.
5. Почему это хорошо работает в ЧГК.
6. Ассоциативные якоря (5–7).

ЗАПРЕТЫ:
— не пересказывать сюжет
— не использовать списки
— не вставлять источники
— не писать «интересный факт»

ИСХОДНЫЙ ФАКТ:
{raw_fact}

ВЫВОД:
Только готовый текст.
"""

    r = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.55,
        max_output_tokens=800,
    )

    return r.output_text.strip()


# ---------- отправка факта ----------
async def send_fact(bot, chat_id, mark=None):
    state = load_state()
    facts = load_facts()

    unused = [f for f in facts if f not in state["used"]]
    if not unused:
        await bot.send_message(chat_id, "Факты закончились.")
        return

    raw = random.choice(unused)
    text = rewrite_fact(raw)

    await bot.send_message(chat_id, text[:4096])

    state["used"].append(raw)
    if mark:
        state["sent"].append(mark)

    save_state(state)


# ---------- команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я присылаю 3 ЧГК-факта в день:\n"
        "🕚 11:00\n🕒 15:00\n🕗 20:00\n\n"
        "Команда /fact — получить факт сразу."
    )


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Готовлю факт…")
    await send_fact(context.bot, update.effective_chat.id)


# ---------- планировщик ----------
async def scheduler(app):
    while True:
        now = datetime.datetime.now().strftime("%H:%M")
        state = load_state()

        if now in SCHEDULE_TIMES and now not in state["sent"]:
            for chat in app.bot_data.get("chats", []):
                await send_fact(app.bot, chat, mark=now)

        await asyncio.sleep(60)


# ---------- запуск ----------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    async def on_startup(app):
        app.bot_data["chats"] = set()

    async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
        app.bot_data["chats"].add(update.effective_chat.id)

    app.add_handler(CommandHandler("start", track_chat))

    app.post_init = on_startup
    app.create_task(scheduler(app))
    app.run_polling()


if __name__ == "__main__":
    main()
