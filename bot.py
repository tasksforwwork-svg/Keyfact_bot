import os
import json
import random
import datetime
import time
import threading
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

SCHEDULE_HOURS = ["11", "15", "20"]
# ==============================================

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------- состояние ----------
def load_state():
    today = str(datetime.date.today())
    if not os.path.exists(STATE_FILE):
        return {"date": today, "sent_hours": [], "used_facts": []}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if state.get("date") != today:
        state["date"] = today
        state["sent_hours"] = []

    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- факты ----------
def load_facts():
    df = pd.read_excel(FACTS_FILE)
    return [
        str(cell).strip()
        for cel
