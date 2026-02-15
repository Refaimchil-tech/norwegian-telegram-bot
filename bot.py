import logging
import sqlite3
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI
import random

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден!")

client = OpenAI(api_key=OPENAI_API_KEY)


logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER UNIQUE,
    level TEXT DEFAULT 'A1'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS words (
    telegram_id INTEGER,
    word TEXT,
    translation TEXT
)
""")

conn.commit()


async def ask_ai(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 'A1')", (user_id,))
    conn.commit()
    await update.message.reply_text("Hei! 🇳🇴 Я твой AI-учитель норвежского.")


async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    word = " ".join(context.args)

    if not word:
        await update.message.reply_text("Напиши: /add bok")
        return

    translation = await ask_ai(f"Переведи слово {word} с норвежского на русский")

    cursor.execute("INSERT INTO words VALUES (?, ?, ?)", (user_id, word, translation))
    conn.commit()

    await update.message.reply_text(f"Слово добавлено ✅\nПеревод: {translation}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    prompt = f"""
Ты преподаватель норвежского языка.
Исправь ошибки:
{text}

Ответь:
1. Исправленный вариант
2. Объяснение
3. Ответ на норвежском
"""

    answer = await ask_ai(prompt)
    await update.message.reply_text(answer)


async def send_lesson(app):
    users = cursor.execute("SELECT telegram_id FROM users").fetchall()

    for user in users:
        user_id = user[0]

        words = cursor.execute(
            "SELECT word FROM words WHERE telegram_id=? ORDER BY RANDOM() LIMIT 3",
            (user_id,)
        ).fetchall()

        word_list = ", ".join([w[0] for w in words])

        prompt = f"""
Создай мини-урок норвежского.
Используй слова: {word_list}
Добавь 3 новых слова.
Добавь мини-викторину.
"""

        lesson = await ask_ai(prompt)
        await app.bot.send_message(chat_id=user_id, text=lesson)


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_word))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: send_lesson(app), "cron", hour=8)
    scheduler.add_job(lambda: send_lesson(app), "cron", hour=12)
    scheduler.add_job(lambda: send_lesson(app), "cron", hour=16)
    scheduler.add_job(lambda: send_lesson(app), "cron", hour=19)
    scheduler.start()

    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
