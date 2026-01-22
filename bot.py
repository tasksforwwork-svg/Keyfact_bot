import os
import json
import random
import datetime
import time
import pandas as pd
from telegram import Bot
from openai import OpenAI

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")  # ОБЯЗАТЕЛЬНО

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

Требования:
— начинается с «Факт — …»
— 8–14 предложений
— плотный интеллектуальный стиль
— без морали и разговорности
— обязательны: контекст, неочевидность, ЧГК-ценность, ассоциативные якоря

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


# ---------- основная логика ----------
def send_scheduled_facts():
    while True:
        now = datetime.datetime.now()
        hour = now.strftime("%H")

        state = load_state()

        if hour in SCHEDULE and hour not in state["sent_slots"]:
            facts = load_facts()
            unused = [f for f in facts if f not in state["used_facts"]]

            if unused:
                raw_fact = random.choice(unused)
                text = rewrite_fact(raw_fact)

                bot.send_message(
                    chat_id=CHAT_ID,
                    text=text[:4096]
                )

                state["used_facts"].append(raw_fact)
                state["sent_slots"].append(hour)
                save_state(state)

        time.sleep(60)


if __name__ == "__main__":
    send_scheduled_facts()
