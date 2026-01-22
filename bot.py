import os
import random
import requests
from bs4 import BeautifulSoup
from telegram.ext import Updater, CommandHandler
from openai import OpenAI

# ================= НАСТРОЙКИ =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BASE_URL = "https://gotquestions.online"
# =============================================

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------- получаем случайный ЧГК-факт ----------
def get_raw_fact():
    main = requests.get(BASE_URL, timeout=15)
    soup = BeautifulSoup(main.text, "html.parser")

    links = [
        a["href"] for a in soup.select("a[href]")
        if a["href"].startswith("/question/")
    ]

    if not links:
        return None

    url = BASE_URL + random.choice(links)
    page = requests.get(url, timeout=15)
    soup = BeautifulSoup(page.text, "html.parser")

    title = soup.find("h1")
    article = soup.find("article")

    if not title or not article:
        return None

    text = article.get_text("\n", strip=True)

    return f"{title.text}\n\n{text}"


# ---------- GPT-редактор ----------
def edit_with_gpt(raw_text):
    prompt = f"""
Ты — редактор ЧГК-досье.

На входе — текст из базы вопросов ЧГК.
Твоя задача — превратить его в компактный,
энциклопедический факт «из того же ряда», что:

- Бульдозерная выставка
- Волшебная гора
- Бутон розы

Требования:
- строгий, интеллектуальный стиль
- без разговорных слов
- без морализаторства
- без вопросов читателю
- 1–2 абзаца
- начинается со слова: «Факт.»

Исходный текст:
{raw_text}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
        temperature=0.6,
    )

    return response.output_text.strip()


# ---------- Telegram ----------
def send_fact(update, context):
    raw = get_raw_fact()

    if not raw:
        update.message.reply_text("Не удалось получить факт. Попробуй позже.")
        return

    try:
        final_text = edit_with_gpt(raw)
    except Exception as e:
        update.message.reply_text("Ошибка при обработке факта.")
        return

    update.message.reply_text(final_text[:4096])


def start(update, context):
    update.message.reply_text(
        "Привет.\nЯ присылаю отредактированные ЧГК-факты.\n\nВот один из них:"
    )
    send_fact(update, context)


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("fact", send_fact))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
