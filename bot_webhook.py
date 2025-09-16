import os
import logging
from flask import Flask, request
import telebot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация - ПРЯМОЕ ПРИСВАИВАНИЕ
TOKEN = "7592969962:AAE93nt3NRENC9LCxfomvONl7zqozS2SZh8"  # НОВЫЙ ТОКЕН
GROUP_ID = -1094323262  # Ваш ID

logger.info("✅ Bot starting with NEW TOKEN...")
logger.info(f"Token: {TOKEN}")
logger.info(f"Group ID: {GROUP_ID}")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Вопросы на двух языках
QUESTIONS = {
    "ru": [
        "Здравствуйте! Пожалуйста, укажите ваше имя:",
        "Укажите адрес объекта:",
        "Ваш номер телефона:",
        "Примерная квадратура (м²):",
        "Оставьте комментарий или фото дома:"
    ],
    "uz": [
        "Assalomu alaykum! Iltimos, ismingizni kiriting:",
        "Obekt manzilini yozing:",
        "Telefon raqamingiz:",
        "Taxminiy maydon (m²):",
        "Izoh yoki uy rasmini yuboring:"
    ]
}

user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        logger.info(f"📨 Received: {message.text}")
        chat_id = message.chat.id
        
        if 'uz' in message.text:
            lang = 'uz'
        else:
            lang = 'ru'
            
        logger.info(f"🌐 Language: {lang} for chat {chat_id}")
        
        user_data[chat_id] = {'lang': lang, 'step': 0, 'answers': []}
        bot.send_message(chat_id, QUESTIONS[lang][0])
        logger.info(f"✅ First question sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("🔄 Webhook received")
        json_data = request.get_json()
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return 'Error', 500

@app.route('/')
def home():
    return '✅ Bot is running with NEW TOKEN!'

if __name__ == '__main__':
    logger.info("🚀 Starting Flask server...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
