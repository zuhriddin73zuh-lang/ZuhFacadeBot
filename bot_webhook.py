# -*- coding: utf-8 -*-
import telebot
from telebot import types
from flask import Flask, request

TOKEN = "7592969962:AAFavNdgwxlyzf-oPRvVeDNLOzfPFjWrjbw"
GROUP_ID = -1002297999589  # твоя группа для заявок

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

STATE = {}  # сохраняем состояние пользователя

# -----------------------
# /start с выбором языка из параметра
# -----------------------
@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()

    lang = "ru"  # по умолчанию русский
    if len(args) > 1:
        param = args[1].lower()
        if param in ["uz", "go_uz"]:
            lang = "uz"
        elif param in ["ru", "go_ru"]:
            lang = "ru"

    # сохраняем язык и состояние
    STATE[message.chat.id] = {"lang": lang, "step": "name"}

    if lang == "ru":
        bot.send_message(message.chat.id, "Здравствуйте! Введите ваше имя:")
    else:
        bot.send_message(message.chat.id, "Salom! Ismingizni kiriting:")

# -----------------------
# Опросник (имя → телефон → комментарий)
# -----------------------
@bot.message_handler(func=lambda m: m.chat.id in STATE)
def form_handler(message):
    user_state = STATE[message.chat.id]
    lang = user_state["lang"]

    if user_state["step"] == "name":
        user_state["name"] = message.text
        user_state["step"] = "phone"
        if lang == "ru":
            bot.send_message(message.chat.id, "Введите ваш номер телефона:")
        else:
            bot.send_message(message.chat.id, "Telefon raqamingizni kiriting:")

    elif user_state["step"] == "phone":
        user_state["phone"] = message.text
        user_state["step"] = "comment"
        if lang == "ru":
            bot.send_message(message.chat.id, "Введите комментарий (или напишите «нет»):")
        else:
            bot.send_message(message.chat.id, "Izoh kiriting (yoki «yo‘q» deb yozing):")

    elif user_state["step"] == "comment":
        user_state["comment"] = message.text

        # -----------------------
        # Заявка в группу (тоже на выбранном языке)
        # -----------------------
        if lang == "ru":
            text = (
                "📩 Новая заявка:\n\n"
                f"👤 Имя: {user_state['name']}\n"
                f"📞 Телефон: {user_state['phone']}\n"
                f"💬 Комментарий: {user_state['comment']}"
            )
            thank = "✅ Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время."
        else:
            text = (
                "📩 Yangi ariza:\n\n"
                f"👤 Ism: {user_state['name']}\n"
                f"📞 Telefon: {user_state['phone']}\n"
                f"💬 Izoh: {user_state['comment']}"
            )
            thank = "✅ Rahmat! Arizangiz qabul qilindi. Tez orada siz bilan bog‘lanamiz."

        bot.send_message(GROUP_ID, text)
        bot.send_message(message.chat.id, thank)

        # очищаем состояние
        del STATE[message.chat.id]

# -----------------------
# Flask webhook
# -----------------------
@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url="https://zuhfacadebot-1.onrender.com/" + TOKEN)
    return "!", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

   

           
        







