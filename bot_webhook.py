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
all_applications = {}  # Для хранения всех заявок по chat_id

# Вопросы на двух языках
QUESTIONS = {
    "ru": [
        "Здравствуйте! Пожалуйста, укажите ваше имя:",
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
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi, tez orada sizga qo‘ng‘iroq qilamiz."
}

# Старт через ссылку с канала: ?start=ru или ?start=uz
@bot.message_handler(commands=['start'])
def start_dialog(message):
    chat_id = message.chat.id
    # Определяем язык через параметр start
    lang = "ru"  # По умолчанию русский
    if message.text.startswith("/start uz"):
        lang = "uz"
    elif message.text.startswith("/start go"):
        lang = "ru"
    elif message.text.startswith("/start info"):
        lang = "ru"  # можно расширить для инфо
    elif message.text.startswith("/start faq"):
        lang = "ru"  # можно расширить для faq

    # Инициализируем состояние
    user_state[chat_id] = {"lang": lang, "step": 0}
    user_data[chat_id] = []

    # Начинаем первый вопрос
    bot.send_message(chat_id, QUESTIONS[lang][0])

# Обработка ответов пользователя
@bot.message_handler(func=lambda message: message.chat.id in user_state)
def handle_answers(message):
    chat_id = message.chat.id
    state = user_state[chat_id]
    lang = state["lang"]
    step = state["step"]

    # Сохраняем ответ
    user_data[chat_id].append(message.text)
    state["step"] += 1

    if state["step"] < len(QUESTIONS[lang]):
        # Следующий вопрос
        bot.send_message(chat_id, QUESTIONS[lang][state["step"]])
    else:
        # Все ответы собраны
        answers = user_data[chat_id]
        application_text = (
            f"📩 Новая заявка\n\n"
            f"👤 Имя: {answers[0]}\n"
            f"🏠 Адрес: {answers[1]}\n"
            f"📞 Телефон: {answers[2]}\n"
            f"📐 Квадратов: {answers[3]}\n"
            f"💬 Комментарий: {answers[4]}"
        )
        # Отправка в группу
        bot.send_message(GROUP_ID, application_text)
        # Сообщение пользователю
        bot.send_message(chat_id, THANK_YOU[lang])

        # Сохраняем в долговременную базу
        all_applications[chat_id] = answers

        # Сброс состояния диалога
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

    

           
        





