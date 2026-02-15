import os
import logging
import random
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка
logging.basicConfig(level=logging.INFO)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash') # Или gemini-2.0-flash-exp

# База данных: теперь храним еще и предпочтительный язык
user_data = {} 

async def get_gemini_response(prompt):
    response = model.generate_content(prompt)
    return response.text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data:
        user_data[user_id] = {"words": [], "lang": "английский"} # По умолчанию

    # Промпт теперь учитывает английский и турецкий
    prompt = f"""
    Ты — международный учитель норвежского. Пользователь написал: "{text}"
    
    Задачи:
    1. Определи язык пользователя (Русский, Фарси, Испанский, Английский или Турецкий).
    2. Ответь на норвежском, а затем ОБЪЯСНИ всё на языке пользователя.
    3. В самом конце сообщения напиши строго одну строку в формате: 
       DETECTED_LANG: [название языка на русском]
    4. Если есть новое слово для списка: ADD_WORD: [слово].
    """
    
    try:
        response = await get_gemini_response(prompt)
        
        # Сохраняем язык для будущих рассылок
        if "DETECTED_LANG:" in response:
            lang = response.split("DETECTED_LANG:")[-1].strip().split('\n')[0]
            user_data[user_id]["lang"] = lang

        # Логика добавления слова
        if "ADD_WORD:" in response:
            word = response.split("ADD_WORD:")[-1].strip().split()[0]
            if word not in user_data[user_id]["words"]:
                user_data[user_id]["words"].append(word)

        # Очищаем текст от технических меток перед отправкой пользователю
        clean_text = response.split("DETECTED_LANG:")[0].split("ADD_WORD:")[0].strip()
        await update.message.reply_text(clean_text)
            
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Sorry, error occurred. / Произошла ошибка.")

# Рассылка на языке пользователя
async def scheduled_message(app):
    for user_id, data in user_data.items():
        user_lang = data.get("lang", "английский")
        prompt = f"Напиши короткий вопрос на норвежском и его перевод на {user_lang}. Объясни одно слово из вопроса на {user_lang}."
        
        try:
            message = await get_gemini_response(prompt)
            await app.bot.send_message(chat_id=user_id, text=f"🇳🇴 Practice time!\n\n{message}")
        except Exception as e:
            logging.error(f"Ошибка рассылки {user_id}: {e}")

def setup_scheduler(app):
    scheduler = AsyncIOScheduler()
    # Рассылка 4 раза в день (пример времени)
    for h in [9, 13, 17, 21]:
        scheduler.add_job(scheduled_message, 'cron', hour=h, minute=0, args=[app])
    scheduler.start()

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Send me a message!")))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    setup_scheduler(application)
    application.run_polling()

if __name__ == "__main__":
    main()
