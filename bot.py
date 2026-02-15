import os
import logging
import random
import asyncio
import google.generativeai as genai
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Переменные из Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# "База данных" в памяти (для Railway лучше использовать БД, но для начала сойдет словарь)
# Структура: { user_id: { "words": ["hallo", "takk"], "chat_history": [...] } }
user_data = {}

# Вспомогательная функция для запросов к Gemini
async def get_gemini_response(prompt, history=[]):
    chat = model.start_chat(history=history)
    response = chat.send_message(prompt)
    return response.text

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"words": [], "history": []}
    
    await update.message.reply_text(
        "Hei! Я твой бот для изучения норвежского. \n"
        "Я буду писать тебе 4 раза в день, проводить викторины и учить с тобой новые слова. \n"
        "Просто напиши мне что-нибудь на норвежском или добавь слово, которое хочешь выучить!"
    )

# Обработка сообщений (Общение и запоминание слов)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data:
        user_data[user_id] = {"words": [], "history": []}

    # Промпт для Gemini, чтобы он выделил новые слова и поддержал диалог
    prompt = f"""
    Ты — учитель норвежского языка. Пользователь написал: "{text}". 
    1. Поддержи диалог на норвежском (с переводом на русский).
    2. Если в сообщении есть новое слово, которое пользователь явно хочет выучить, напиши в конце строки: "ADD_WORD: [слово]".
    3. Веди себя дружелюбно.
    """
    
    response = await get_gemini_response(prompt)
    
    # Проверка, нужно ли добавить слово в список
    if "ADD_WORD:" in response:
        word = response.split("ADD_WORD:")[-1].strip()
        if word not in user_data[user_id]["words"]:
            user_data[user_id]["words"].append(word)

    await update.message.reply_text(response.replace(f"ADD_WORD: {word if 'word' in locals() else ''}", ""))

# Функция для рассылки (Спрашивает что-то на норвежском)
async def scheduled_message(app):
    for user_id in user_data.keys():
        prompt = "Напиши короткий вопрос на норвежском для ученика (уровень А1-А2), чтобы завязать диалог. Напиши перевод на русский."
        message = await get_gemini_response(prompt)
        try:
            await app.bot.send_message(chat_id=user_id, text=f"🇳🇴 Время практики!\n\n{message}")
        except Exception as e:
            print(f"Не удалось отправить сообщение {user_id}: {e}")

# Функция для викторины
async def send_quiz(app):
    for user_id, data in user_data.items():
        if not data["words"]:
            prompt = "Придумай викторину: напиши 1 норвежское слово и 3 варианта перевода (один правильный)."
        else:
            word_to_test = random.choice(data["words"])
            prompt = f"Сделай викторину для слова '{word_to_test}'. Напиши слово и 3 варианта перевода."
        
        quiz_text = await get_gemini_response(prompt)
        try:
            await app.bot.send_message(chat_id=user_id, text=f"🧠 Викторина!\n\n{quiz_text}")
        except Exception as e:
            print(f"Не удалось отправить викторину {user_id}: {e}")

# Настройка планировщика (4 раза в день)
def setup_scheduler(app):
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Рассылка вопросов в 10:00, 14:00, 18:00
    times = ["10:00", "14:00", "18:00"]
    for t in times:
        hour, minute = map(int, t.split(":"))
        scheduler.add_job(scheduled_message, 'cron', hour=hour, minute=minute, args=[app])
    
    # Викторина в 21:00
    scheduler.add_job(send_quiz, 'cron', hour=21, minute=0, args=[app])
    
    scheduler.start()

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Хендлеры
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Запуск планировщика
    setup_scheduler(application)
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
