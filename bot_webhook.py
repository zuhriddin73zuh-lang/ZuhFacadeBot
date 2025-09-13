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
        "Как вас зовут?",
        "Укажите адрес:",
        "Ваш номер телефона:",
        "Сколько квадратов?",
        "Оставьте комментарий:"
    ],
    "uz": [
        "Ismingizni kiriting:",
        "Manzilingizni yozing:",
        "Telefon raqamingiz:",
        "Necha kvadrat?",
        "Izoh qoldiring:"
    ]
}

THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi."
}

LANGUAGE_SELECT = "Выберите язык / Tilni tanlang:"

# Начало диалога — выбор языка
@bot.message_handler(func=lambda m: True, content_types=['text'])
def start_dialog(message):
    if message.chat.id not in user_state:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru"))
        markup.add(types.InlineKeyboardButton("O‘zbekcha 🇺🇿", callback_data="lang_uz"))
        bot.send_message(message.chat.id, LANGUAGE_SELECT, reply_markup=markup)

# Обработка выбора языка
@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def handle_language(call):
    lang = call.data.split("_")[1]
    user_state[call.message.chat.id] = {"lang": lang, "step": 0}
    user_data[call.message.chat.id] = []
    bot.send_message(call.message.chat.id, QUESTIONS[lang][0])

# Обработка ответов пользователя
@bot.message_handler(func=lambda message: message.chat.id in user_state)
def handle_answers(message):
    chat_id = message.chat.id
    state = user_state[chat_id]
    lang = state["lang"]
    step = state["step"]

    user_data[chat_id].append(message.text)
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

           
        




