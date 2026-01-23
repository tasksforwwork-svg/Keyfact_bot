import os
import json
import random
import datetime
import pandas as pd

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from openai import OpenAI


# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FACTS_FILE = "facts.xlsx"
STATE_FILE = "state.json"

SEND_TIMES = [11, 15, 20]  # часы отправки
# ===============================================


client = OpenAI(api_key=OPENAI_API_KEY)


# ================== СОСТОЯНИЕ ==================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ================== ФАКТЫ ==================
def load_facts():
    df = pd.read_excel(FACTS_FILE)
    return [
        str(x).strip()
        for x in df.iloc[:, 0]
        if isinstance(x, str) and x.strip()
    ]


# ================== GPT-РЕДАКТОР ==================
COOL_BINGO_PROMPT = """
Ты редактор ЧГК-паблика Cool Bingo.

Оформи материал строго в формате ЧГК-досье.

СТРУКТУРА:
Факт —
(название)

Краткое определение — 1–2 предложения.

Историко-культурный контекст —
что это, где и почему возникло.

Неочевидные детали —
парадоксы, символика, скрытые смыслы.

Связи с другими областями —
литература, кино, философия, наука, политика.

Почему это хорошо работает в ЧГК —
как используется в вопросах.

Ассоциативные якоря —
чем маскируется, какие ложные ходы.

ТРЕБОВАНИЯ:
— 12–18 предложений
— энциклопедический стиль
— без разговорных слов
— без морали и оценок
— абзацы ОБЯЗАТЕЛЬНЫ
— без эмодзи
— без списков

Исходный факт:
"""


def rewrite_fact(raw_fact: str) -> str:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=COOL_BINGO_PROMPT + raw_fact,
        temperature=0.5,
    )
    return response.output_text.strip()


# ================== ОТПРАВКА ==================
async def send_fact(chat_id: int, context: ContextTypes.DEFAULT_TYPE, mark: str | None = None):
    state = load_state()
    today = str(datetime.date.today())

    if str(chat_id) not in state:
        state[str(chat_id)] = {
            "date": today,
            "sent_marks": [],
            "used_facts": [],
        }

    chat_state = state[str(chat_id)]

    if chat_state["date"] != today:
        chat_state["date"] = today
        chat_state["sent_marks"] = []

    if mark and mark in chat_state["sent_marks"]:
        return

    facts = load_facts()
    unused = [f for f in facts if f not in chat_state["used_facts"]]

    if not unused:
        await context.bot.send_message(chat_id, "Факты закончились.")
        return

    raw = random.choice(unused)
    text = rewrite_fact(raw)

    await context.bot.send_message(chat_id, text[:4096])

    chat_state["used_facts"].append(raw)
    if mark:
        chat_state["sent_marks"].append(mark)

    save_state(state)


# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    job_queue = context.application.job_queue

    # очищаем старые задачи
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
        "Готово.\n\n"
        "Я присылаю 3 ЧГК-факта в день:\n"
        "🕚 11:00\n🕒 15:00\n🕗 20:00\n\n"
        "Команда /fact — получить факт вручную."
    )


async def manual_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_fact(update.effective_chat.id, context)


# ================== JOB ==================
async def send_scheduled_fact(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await send_fact(job.chat_id, context, mark=job.name)


# ================== ЗАПУСК ==================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fact", manual_fact))

    app.run_polling()


if __name__ == "__main__":
    main()
