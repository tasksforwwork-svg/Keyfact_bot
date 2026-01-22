import os
import json
import random
import datetime
import time
import pandas as pd
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from openai import OpenAI

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

FACTS_FILE = "facts.xlsx"
STATE_FILE = "state.json"

SCHEDULE = {
    "11": 0,
    "15": 1,
    "20": 2
}
# ==============================================

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)


# ---------- состояние ----------
def load_state():
    today = str(datetime.date.today())
    if not os.path.exists(STATE_FILE):
        return {"date": today, "sent_slots": [], "used_facts": []}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if state.get("date") != today:
        state["date"] = today
        state["sent_slots"] = []

    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- факты ----------
def load_facts():
    df = pd.read_excel(FACTS_FILE)
    return [
        str(cell).strip()
        for cell in df.iloc[:, 0]
        if isinstance(cell, str) and cell.strip()
    ]


# ---------- GPT ----------
def rewrite_fact(raw_fact):
    prompt = f"""
Ты редактор ЧГК-паблика Cool Bingo.

Перепиши факт в формате ЧГК-досье.

Формат:
Факт — …

Структура:
1. Краткое определение
2. Историко-культурный контекст
3. Неочевидные детали
4. Связи с другими областями
5. Почему это хорошо работает в ЧГК
6. Ассоциативные якоря

Требования:
— 8–14 предложений
— энциклопедический стиль
— без разговорных слов
— без морали

Исходный факт:
{raw_fact}

Выводи только готовый текст.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.55
    )

    return response.output_text.strip()


# ---------- отправка факта ----------
def send_fact(mark_slot: str | None = None):
    state = load_state()
    facts = load_facts()
    unused = [f for f in facts if f not in state["used_facts"]]

    if not unused:
        return

    raw_fact = random.choice(unused)
    text = rewrite_fact(raw_fact)

    bot.send_message(chat_id=CHAT_ID, text=text[:4096])

    state["used_facts"].append(raw_fact)
    if mark_slot:
        state["sent_slots"].append(mark_slot)

    save_state(state)


# ---------- расписание ----------
def scheduled_loop():
    while True:
        now = datetime.datetime.now()
        hour = now.strftime("%H")

        state = load_state()

        if hour in SCHEDULE and hour not in state["sent_slots"]:
            send_fact(mark_slot=hour)

        time.sleep(60)


# ---------- команды ----------
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Я присылаю 3 ЧГК-факта в день:\n"
        "11:00, 15:00 и 20:00.\n\n"
        "Команда /fact — получить факт прямо сейчас."
    )


def manual_fact(update: Update, context: CallbackContext):
    send_fact()
    update.message.reply_text("☝️ Вот ваш факт.")


# ---------- запуск ----------
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("fact", manual_fact))

    updater.start_polling()

    scheduled_loop()


if __name__ == "__main__":
    main()
