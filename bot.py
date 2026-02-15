import os
import logging
import random
import io
from groq import Groq
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройка
logging.basicConfig(level=logging.INFO)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Инициализация Groq
client = Groq(api_key=GROQ_API_KEY)
# Используем Llama 3 — она отлично справляется с норвежским
MODEL_NAME = "llama-3.3-70b-versatile"

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

async def get_groq_response(prompt):
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Groq Error: {e}")
        return "Sorry, I'm pooping... Text me later."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"words": [], "lang": "English", "level": "B2 Prep"}
    await update.message.reply_text(
        "Hei! I am your Groq-powered Norwegian tutor for B2 level. Choose your language:",
        reply_markup=get_language_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data or "lang" not in user_data[user_id]:
        await update.message.reply_text("Пожалуйста, выберите язык через /start")
        return

    chosen_lang = user_data[user_id]["lang"]

    # КОМБИНИРОВАННЫЙ ПРОМПТ: КОНТРОЛЬ B2 + ИСПРАВЛЕНИЕ + ПЕРЕВОД
    prompt = f"""
    Ты — эксперт по Norskprøve B2. Ученик выбрал язык для объяснений: {chosen_lang}.
    Сообщение ученика: "{text}"
    
    ТВОЙ СТРОГИЙ ПЛАН ОТВЕТА:
    1. RETTING (ИСПРАВЛЕНИЕ): Проверь грамматику, порядок слов и лексику. 
       - Если есть ошибки, напиши: "Riktig: [исправленная фраза]". 
       - Дай краткое объяснение ошибки и ПЕРЕВОД этого объяснения на {chosen_lang}.
       - Если ошибок нет: "Perfekt! Ingen feil."
    
    2. SVAR (ОТВЕТ): Ответь на норвежском (уровень B2: сложные союзы, официальный стиль). 
       - Обязательно добавь ПЕРЕВОД своего ответа на {chosen_lang}.
    
    3. GRAMMATIKK-TIPS: Дай один очень короткий совет по грамматике уровня B2 на языке {chosen_lang}.
    
    4. ADD_WORD: [слово уровня B2].
    
    ПРАВИЛА:
    - Всего НЕ БОЛЕЕ 5-6 предложений.
    - Перевод на {chosen_lang} обязателен для каждого раздела.
    - Будь быстр и точен.
    """
    
    response_text = await get_groq_response(prompt)
    
    
    # Обработка слов
    if "ADD_WORD:" in response_text:
        word = response_text.split("ADD_WORD:")[-1].strip().split()[0]
        if word not in user_data[user_id]["words"]:
            user_data[user_id]["words"].append(word)

    clean_text = response_text.split("ADD_WORD:")[0].strip()
    await update.message.reply_text(clean_text)

    # Добавим автоматический голосовой ответ для практики слуха
    try:
        # Озвучиваем только норвежскую часть (первое предложение)
        norwegian_part = clean_text.split('.')[0]
        tts = gTTS(text=norwegian_part, lang='no')
        voice_io = io.BytesIO()
        tts.write_to_fp(voice_io)
        voice_io.seek(0)
        await update.message.reply_voice(voice=voice_io)
    except:
        pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data[user_id]["lang"] = query.data.split('_')[1]
    await query.edit_message_text(f"Language set to {user_data[user_id]['lang']}. Let's practice for B2!")

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^lang_'))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Планировщик остается прежним
    scheduler = AsyncIOScheduler()
    # (Добавь сюда задачи рассылки из предыдущего кода)
    
    application.run_polling()

if __name__ == "__main__":
    main()
