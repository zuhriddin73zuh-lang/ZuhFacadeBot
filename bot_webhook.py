
import os
import logging
from flask import Flask, request
import telebot
from telebot import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))
PORT = int(os.environ.get("PORT", 5000))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

QUESTIONS = {
    "ru": [
        "Укажите ваше имя:",
        "Адрес объекта:",
        "Ваш номер телефона:",
        "Примерная квадратура (м²):",
        "Комментарий или фото:"
    ],
    "uz": [
        "Ismingizni kiriting:",
        "Obyekt manzilini yozing:",
        "Telefon raqamingiz:",
        "Taxminiy maydon (m²):",
        "Izoh yoki rasm:"
    ]
}

THANK_YOU = {
    "ru": "✅ Спасибо! Мы свяжемся с вами.",
    "uz": "✅ Rahmat! Bog'lanamiz."
}

user_data = {}

# Обработчик для кнопок "Русский" и "Узбекский"
@bot.message_handler(func=lambda m: m.text in ["Русский", "Узбекский"])
def handle_language_selection(message):
    chat_id = message.chat.id
    lang = "ru" if message.text == "Русский" else "uz"
    
    user_data[chat_id] = {"lang": lang, "step": 0, "answers": []}
    bot.send_message(chat_id, QUESTIONS[lang][0])

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        return  # Игнорируем сообщения не из диалога

    user = user_data[chat_id]
    lang = user["lang"]
    user["answers"].append(message.text)
    user["step"] += 1

    if user["step"] < len(QUESTIONS[lang]):
        bot.send_message(chat_id, QUESTIONS[lang][user["step"]])
    else:
        try:
            name, address, phone, square, comment = user["answers"]
            text = f"👤 {name}\n🏠 {address}\n📞 {phone}\n📐 {square}\n💬 {comment}"
            bot.send_message(GROUP_ID, text)
            bot.send_message(chat_id, THANK_YOU[lang])
            del user_data[chat_id]
        except Exception as e:
            logger.error(f"Error: {e}")
            bot.send_message(chat_id, "❌ Ошибка.")

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return 'OK'

@app.route('/')
def home():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=PORT)






