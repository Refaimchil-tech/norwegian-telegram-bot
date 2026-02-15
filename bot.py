import os
import logging
import random
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Логирование
logging.basicConfig(level=logging.INFO)

# Ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# База данных пользователей
user_data = {}

async def get_gemini_response(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "Error."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    text = update.message.text

    if user_id not in user_data:
        # Теперь не ставим "русский" по умолчанию, а ждем определения
        user_data[user_id] = {"words": [], "lang": "English"} 

    # ЖЕСТКИЙ ПРОМПТ НА СОБЛЮДЕНИЕ ЯЗЫКА
    prompt = f"""
    Ты — учитель норвежского. Твое общение строится в формате микро-диалогов (до 5 предложений).
    
    ИНСТРУКЦИЯ ПО ЯЗЫКУ:
    1. Определи язык, на котором пишет пользователь: {text}.
    2. ТЫ ОБЯЗАН отвечать и давать все объяснения ТОЛЬКО на этом языке (Russian, Farsi, Spanish, English, or Turkish).
    3. ЗАПРЕЩЕНО использовать русский, если пользователь пишет на английском или турецком.
    
    СТРУКТУРА ОТВЕТА:
    - Фраза на норвежском.
    - Перевод и краткое пояснение (1-2 предложения) на языке пользователя.
    - Если есть новое слово: ADD_WORD: [слово].
    - В конце метка: DETECTED_LANG: [название языка на английском].
    """
    
    response = await get_gemini_response(prompt)
    
    # Техническая обработка ответа
    if "DETECTED_LANG:" in response:
        detected = response.split("DETECTED_LANG:")[-1].strip().split('\n')[0]
        user_data[user_id]["lang"] = detected
    
    if "ADD_WORD:" in response:
        word_part = response.split("ADD_WORD:")[-1].strip().split()[0]
        if word_part not in user_data[user_id]["words"]:
            user_data[user_id]["words"].append(word_part)

    # Чистим текст
    final_text = response.split("DETECTED_LANG:")[0].split("ADD_WORD:")[0].strip()
    await update.message.reply_text(final_text)

# Рассылка на языке, который бот запомнил для этого юзера
async def scheduled_message(app):
    for user_id, data in user_data.items():
        user_lang = data.get("lang", "English")
        prompt = f"Give one short Norwegian sentence and its translation into {user_lang}. Short explanation in {user_lang}. Max 3 sentences total."
        
        message = await get_gemini_response(prompt)
        try:
            await app.bot.send_message(chat_id=user_id, text=f"🇳🇴 Quick Practice:\n\n{message}")
        except:
            continue

def setup_scheduler(app):
    scheduler = AsyncIOScheduler()
    # Рассылка 4 раза в день
    for h in [10, 14, 18, 22]:
        scheduler.add_job(scheduled_message, 'cron', hour=h, minute=0, args=[app])
    scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hei! I'm your Norwegian tutor. Write to me in your language!")

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    setup_scheduler(application)
    application.run_polling()

if __name__ == "__main__":
    main()
