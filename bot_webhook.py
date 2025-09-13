 # -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
from flask import Flask, request

# Переменные окружения (Render)
TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Хранение состояния пользователей
user_state = {}
user_data = {}

# Вопросы на двух языках
QUESTIONS = {
    "ru": [
        "Здравствуйте! Как вас зовут?",
        "Укажите адрес:",
        "Ваш номер телефона:",
        "Сколько квадратов?",
        "Оставьте комментарий:"
    ],
    "uz": [
        "Assalomu alaykum! Ismingizni kiriting:",
        "Manzilingizni yozing:",
        "Telefon raqamingiz:",
        "Necha kvadrat?",
        "Izoh qoldiring:"
    ]
}

THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята, мы вам скоро позвоним.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi, tez orada sizga qo'ng'iroq qilamiz."
}

# Начало диалога после перехода с канала
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    args = message.text.split()
    # Определяем язык по кнопке канала: ?start=go_rus или ?start=go_uz
    lang = "ru"  # по умолчанию русский
    if len(args) > 1:
        if "uz" in args[1].lower():
            lang = "uz"
    user_state[chat_id] = {"lang": lang, "step": 0}
    user_data[chat_id] = []
    bot.send_message(chat_id, QUESTIONS[lang][0])

# Обработка ответов пользователя
@bot.message_handler(func=lambda message: message.chat.id in user_state)
def handle_answers(message):
    chat_id = message.chat.id
    if message.content_type != 'text':
        bot.send_message(chat_id, "⚠️ Пожалуйста, отвечайте текстом.")
        return

    state = user_state[chat_id]
    lang = state["lang"]
    step = state["step"]

    user_data[chat_id].append(message.text.strip())
    state["step"] += 1

    if state["step"] < len(QUESTIONS[lang]):
        bot.send_message(chat_id, QUESTIONS[lang][state["step"]])
    else:
        # Все ответы собраны
        answers = user_data[chat_id]
        application = (
            f"📩 Новая заявка\n\n"
            f"👤 Имя: {answers[0]}\n"
            f"🏠 Адрес: {answers[1]}\n"
            f"📞 Телефон: {answers[2]}\n"
            f"📐 Квадратов: {answers[3]}\n"
            f"💬 Комментарий: {answers[4]}"
        )
        bot.send_message(GROUP_ID, application)
        bot.send_message(chat_id, THANK_YOU[lang])

        # Сброс состояния
        user_state.pop(chat_id)
        user_data.pop(chat_id)

# Flask webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    if not request.is_json:
        return "unsupported", 403
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
   

           
        






