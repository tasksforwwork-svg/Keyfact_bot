import os
import json
import random
import datetime
import pandas as pd
from telegram.ext import Updater, CommandHandler
from openai import OpenAI

# ========= НАСТРОЙКИ =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FACTS_FILE = "facts.xlsx"
STATE_FILE = "state.json"
# =============================

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------- состояние ----------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"last_date": None, "used_facts": []}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- загрузка фактов ----------
def load_facts():
    df = pd.read_excel(FACTS_FILE)
    facts = [str(x).strip() for x in df.iloc[:, 0] if isinstance(x, str)]
    return facts


# ---------- GPT-редактор ----------
def edit_fact_with_gpt(fact):
    prompt = f"""
Ты — интеллектуальный редактор ЧГК.

Отредактируй факт:
{fact}

Требования:
— энциклопедический стиль
— без разговорных слов
— добавить контекст и неочевидные детали
— не выдумывать факты
— не менять смысл
— плотный, умный текст

Выводи только готовый текст.
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        temperature=0.6,
    )

    return response.output_text.strip()


# ---------- 3 факта дня ----------
def send_daily_facts(update, context):
    state = load_state()
    today = str(datetime.date.today())

    if state["last_date"] == today:
        return

    facts = load_facts()
    unused = [f for f in facts if f not in state["used_facts"]]

    if not unused:
        update.message.reply_text("Факты закончились.")
        return

    facts_today = random.sample(unused, min(3, len(unused)))

    for fact in facts_today:
        edited = edit_fact_with_gpt(fact)
        update.message.reply_text(edited[:4096])
        state["used_facts"].append(fact)

    state["last_date"] = today
    save_state(state)


# ---------- команды ----------
def start(update, context):
    update.message.reply_text(
        "Привет. Я буду присылать тебе 3 ЧГК-факта в день."
    )
    send_daily_facts(update, context)


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
