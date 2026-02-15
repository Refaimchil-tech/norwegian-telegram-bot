import os
import logging
import random
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# База данных в памяти
user_data = {}

def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("Русский", callback_data='lang_Russian'),
         InlineKeyboardButton("English", callback_data='lang_English')],
        [InlineKeyboardButton("Türkçe", callback_data='lang_Turkish'),
         InlineKeyboardButton("Español", callback_data='lang_Spanish')],
        [InlineKeyboardButton("فارسی (Farsi)", callback_data='lang_Farsi')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_gemini_response(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "Feil med AI-tilkobling."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"words": [], "lang": "English", "level_score": 0}
    await update.message.reply_text(
        "Hei! Я подготовлю тебя к Norskprøve B2. Выбери свой родной язык для объяснений:",
        reply_markup=get_language_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_lang = query.data.split('_')[1]
    
    if user_id not in user_data:
        user_data[user_id] = {"words": [], "lang": selected_lang, "level_score": 0}
    else:
        user_data[user_id]["lang"] = selected_lang
        
    await query.edit_message_text(
        f"Valgt språk: {selected_lang}. \n\n"
        "Я буду оценивать твои ответы и постепенно усложнять норвежский до уровня B2. "
        "Давай начнем! Напиши что-нибудь на норвежском."
    )

async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"words": [], "lang": "English", "level_score": 0}
    await update.message.reply_text("Memory reset! Start over with /start")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data:
        user_data[user_id] = {"words": [], "lang": "English", "level_score": 0}

    current_lang = user_data[user_id]["lang"]

    # ПРОМПТ ДЛЯ ПОДГОТОВКИ К B2
    prompt = f"""
    Ты — эксперт по подготовке к экзамену Norskprøve (уровень B2).
    Твой ученик говорит на {current_lang}. Его сообщение: "{text}"
    
    ТВОИ ЗАДАЧИ:
    1. Оцени уровень норвежского в сообщении. Если там ошибки, вежливо исправь их, объясняя правило на {current_lang}.
    2. Отвечай на норвежском, используя лексику и грамматику уровня B2 (используй союзы som, ат, fordi, выражения типа 'på den одной siden').
    3. Поддерживай диалог так, чтобы выстроить подготовку к устной или письменной части экзамена (темы: работа, экология, политика, образование).
    4. Все объяснения и перевод давай СТРОГО на {current_lang}.
    5. Будь кратким (максимум 5-6 предложений).
    6. Если есть полезное слово для B2: ADD_WORD: [слово].
    """
    
    response = await get_gemini_response(prompt)
    
    if "ADD_WORD:" in response:
        word_part = response.split("ADD_WORD:")[-1].strip().split()[0]
        if word_part not in user_data[user_id]["words"]:
            user_data[user_id]["words"].append(word_part)

    clean_text = response.split("ADD_WORD:")[0].strip()
    await update.message.reply_text(clean_text)

async def scheduled_message(app):
    for user_id, data in user_data.items():
        user_lang = data.get("lang", "English")
        # Темы для B2
        topics = ["arbeidsliv", "utdanning", "miljøvern", "norsk politikk", "velferdssamfunnet"]
        topic = random.choice(topics)
        
        prompt = f"""
        Напиши сложный вопрос на норвежском (уровень B2) на тему '{topic}'.
        Добавь перевод вопроса и краткую подсказку, какие аргументы можно использовать, на языке {user_lang}.
        Всего 3-4 предложения.
        """
        
        message = await get_gemini_response(prompt)
        try:
            await app.bot.send_message(chat_id=user_id, text=f"🎓 Norskprøve B2 Trening ({topic}):\n\n{message}")
        except:
            continue

def setup_scheduler(app):
    scheduler = AsyncIOScheduler()
    for h in [10, 14, 18, 22]:
        scheduler.add_job(scheduled_message, 'cron', hour=h, minute=0, args=[app])
    scheduler.start()

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_memory))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^lang_'))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    setup_scheduler(application)
    application.run_polling()

if __name__ == "__main__":
    main()
