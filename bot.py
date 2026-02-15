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

# Клавиатура выбора языка
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
        return "Error connection to AI."

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"words": [], "lang": "English"}
    await update.message.reply_text(
        "Hei! Выбери язык, на котором я буду объяснять тебе норвежский:",
        reply_markup=get_language_keyboard()
    )

# Обработка выбора языка с кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_lang = query.data.split('_')[1]
    
    if user_id not in user_data:
        user_data[user_id] = {"words": [], "lang": selected_lang}
    else:
        user_data[user_id]["lang"] = selected_lang
        
    await query.edit_message_text(f"Perfect! Now I will explain everything in {selected_lang}. Write me something in Norwegian or your language!")

# Команда /reset
async def reset_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"words": [], "lang": "English"}
    await update.message.reply_text("Memory cleared! Language reset to English.", reply_markup=get_language_keyboard())

# Основной обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data:
        user_data[user_id] = {"words": [], "lang": "English"}

    current_lang = user_data[user_id]["lang"]

    # Жесткий промпт, чтобы бот не переключался на другие языки
    prompt = f"""
    Ты — учитель норвежского. Твой ученик говорит на языке: {current_lang}.
    Сообщение ученика: "{text}"
    
    ПРАВИЛА:
    1. Ответ СТРОГО на языке: {current_lang}. Категорически запрещено использовать другие языки для объяснений.
    2. Формат: Короткая фраза на норвежском + перевод и мини-пояснение на {current_lang}.
    3. Максимум 5 предложений.
    4. Если есть новое слово: ADD_WORD: [слово].
    """
    
    response = await get_gemini_response(prompt)
    
    # Сохранение слова
    if "ADD_WORD:" in response:
        word_part = response.split("ADD_WORD:")[-1].strip().split()[0]
        if word_part not in user_data[user_id]["words"]:
            user_data[user_id]["words"].append(word_part)

    clean_text = response.split("ADD_WORD:")[0].strip()
    await update.message.reply_text(clean_text)

# Рассылка (4 раза в день)
async def scheduled_message(app):
    for user_id, data in user_data.items():
        user_lang = data.get("lang", "English")
        prompt = f"Write one short Norwegian question and its translation/explanation in {user_lang}. Max 3 sentences."
        message = await get_gemini_response(prompt)
        try:
            await app.bot.send_message(chat_id=user_id, text=f"🇳🇴 Norwegian Practice:\n\n{message}")
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
    
    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
