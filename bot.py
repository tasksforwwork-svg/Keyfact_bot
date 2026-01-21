import os
import json
import datetime
import random
from telegram.ext import Updater, CommandHandler
import openai

# ================== НАСТРОЙКИ ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

FACTS_PATH = "facts.txt"
STATE_FILE = "state.json"
# ==============================================

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------- работа с состоянием ----------
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
    with open("facts.txt", "r", encoding="utf-8") as f:
        text = f.read()

    facts = [f.strip() for f in text.split("Факт -") if f.strip()]
    return facts


# ---------- генерация текста ----------
def generate_text(fact):
    prompt = f"""
Ты пишешь текст в формате ЧГК-досье.

Факт:
{fact}

Требования к стилю:
- энциклопедический
- без разговорных слов
- без морали
- плотный, интеллектуальный текст

Структура:
1. Краткое определение
2. Историко-культурный контекст
3. Неочевидные детали и перекрёстные отсылки
4. Почему этот факт хорош для ЧГК
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
        temperature=0.7,
    )

    return response.output_text


# ---------- логика "факт дня" ----------
def send_daily_fact(update, context):
    state = load_state()
    today = str(datetime.date.today())

    if state["last_date"] == today:
        update.message.reply_text("Факт дня уже был сегодня 🙂")
        return

    facts = load_facts()
    unused = [f for f in facts if f not in state["used_facts"]]

    if not unused:
        update.message.reply_text("Факты закончились.")
        return

    fact = random.choice(unused)
    text = generate_text(fact)

    update.message.reply_text(text[:4096])

    state["last_date"] = today
    state["used_facts"].append(fact)
    save_state(state)


# ---------- команды ----------
def start(update, context):
    update.message.reply_text(
        "Привет! Я буду присылать тебе один ЧГК-факт в день.\n"
        "Первый — прямо сейчас."
    )
    send_daily_fact(update, context)


# ---------- запуск ----------
def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("fact", send_daily_fact))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()


