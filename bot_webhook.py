# -*- coding: utf-8 -*-
import os
import telebot
from flask import Flask, request

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "7592969962:AAE93nt3NRENC9LCxfomvONl7zqozS2SZh8")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "-4878488268")  # группа для заявок
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://zuhfacadebot-1.onrender.com/webhook")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# Хранилище состояний
STATE = {}

# Тексты на двух языках
TEXTS = {
    "ru": {
        "ask_name": "👋 Здравствуйте! Введите, пожалуйста, ваше имя:",
        "ask_phone": "📞 Теперь введите ваш номер телефона:",
        "ask_address": "📍 Укажите адрес объекта:",
        "ask_square": "📐 Введите квадратуру фасада (в м²):",
        "ask_comment": "💬 Оставьте комментарий (например, вид фасадных работ):",
        "done": "✅ Спасибо! Ваша заявка принята. Мы скоро свяжемся с вами!",
    },
    "uz": {
        "ask_name": "👋 Assalomu alaykum! Iltimos, ismingizni kiriting:",
        "ask_phone": "📞 Endi telefon raqamingizni kiriting:",
        "ask_address": "📍 Ob'ekt manzilini kiriting:",
        "ask_square": "📐 Fasadning kvadraturasini kiriting (m²):",
        "ask_comment": "💬 Izoh qoldiring (masalan, fasad ishlari turi):",
        "done": "✅ Rahmat! So‘rovingiz qabul qilindi. Tez orada siz bilan bog‘lanamiz!",
    }
}


# === Хэндлеры ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    lang = "ru"  # язык по умолчанию
    if message.text.startswith("/start uz"):
        lang = "uz"

    STATE[message.chat.id] = {"step": "name", "lang": lang, "data": {}}
    bot.send_message(message.chat.id, TEXTS[lang]["ask_name"])


@bot.message_handler(func=lambda m: True)
def handle_all(message):
    user_id = message.chat.id

    if user_id not in STATE:
        bot.send_message(user_id, "Напишите /start чтобы начать снова.")
        return

    step = STATE[user_id]["step"]
    lang = STATE[user_id]["lang"]

    if step == "name":
        STATE[user_id]["data"]["name"] = message.text
        STATE[user_id]["step"] = "phone"
        bot.send_message(user_id, TEXTS[lang]["ask_phone"])

    elif step == "phone":
        STATE[user_id]["data"]["phone"] = message.text
        STATE[user_id]["step"] = "address"
        bot.send_message(user_id, TEXTS[lang]["ask_address"])

    elif step == "address":
        STATE[user_id]["data"]["address"] = message.text
        STATE[user_id]["step"] = "square"
        bot.send_message(user_id, TEXTS[lang]["ask_square"])

    elif step == "square":
        STATE[user_id]["data"]["square"] = message.text
        STATE[user_id]["step"] = "comment"
        bot.send_message(user_id, TEXTS[lang]["ask_comment"])

    elif step == "comment":
        STATE[user_id]["data"]["comment"] = message.text

        # Достаём все данные
        name = STATE[user_id]["data"]["name"]
        phone = STATE[user_id]["data"]["phone"]
        address = STATE[user_id]["data"]["address"]
        square = STATE[user_id]["data"]["square"]
        comment = STATE[user_id]["data"]["comment"]

        # Формируем заявку
        text = (
            f"📩 Новая заявка:\n\n"
            f"👤 Имя: {name}\n"
            f"📞 Телефон: {phone}\n"
            f"📍 Адрес: {address}\n"
            f"📐 Квадратура: {square} м²\n"
            f"💬 Комментарий: {comment}"
        )
        bot.send_message(GROUP_CHAT_ID, text)

        # Ответ пользователю
        bot.send_message(user_id, TEXTS[lang]["done"])

        # Чистим состояние
        del STATE[user_id]


# === Flask routes ===
@app.route('/' , methods=['GET'])
def index():
    return "Bot is running!", 200


@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


# Установка вебхука при старте
with app.app_context():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))









