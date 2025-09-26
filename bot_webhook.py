import os
import logging
from flask import Flask, request
import telebot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "7592969962:AAE93nt3NRENC9LCxfomvONl7zqozS2SZh8"
GROUP_ID = -4878488268  # 🎉 ПРАВИЛЬНЫЙ ID ГРУППЫ!

logger.info("✅ Bot starting...")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

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

THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi. Tez orada siz bilan bog'lanamiz."
}

user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        chat_id = message.chat.id
        lang = 'uz' if 'uz' in message.text else 'ru'
        user_data[chat_id] = {'lang': lang, 'step': 0, 'answers': []}
        bot.send_message(chat_id, QUESTIONS[lang][0])
    except Exception as e:
        logger.error(f"Error: {e}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        chat_id = message.chat.id
        if chat_id not in user_data:
            return
            
        user = user_data[chat_id]
        user['answers'].append(message.text)
        user['step'] += 1
        
        if user['step'] < len(QUESTIONS[user['lang']]):
            bot.send_message(chat_id, QUESTIONS[user['lang']][user['step']])
        else:
            # 📤 ОТПРАВЛЯЕМ ЗАЯВКУ В ГРУППУ!
            name, address, phone, square, comment = user['answers']
            
            if user['lang'] == 'ru':
                text = f"📋 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратура: {square}\n💬 Комментарий: {comment}"
            else:
                text = f"📋 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Maydon: {square}\n💬 Izoh: {comment}"
            
            # Отправляем в группу
            bot.send_message(GROUP_ID, text)
            # Подтверждаем пользователю
            bot.send_message(chat_id, THANK_YOU[user['lang']])
            
            del user_data[chat_id]
            
    except Exception as e:
        logger.error(f"Error: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/')
def home():
    return '✅ Bot is running!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

