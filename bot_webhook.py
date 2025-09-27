import os
import logging
from flask import Flask, request
import telebot
from telebot import types

# 🔹 Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 🔹 Конфиг из окружения Render
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_ID"))
PORT = int(os.environ.get("PORT", 5000))

logger.info(f"✅ Bot starting with GROUP_ID={GROUP_ID}")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 🔹 Вопросы
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
        "Obyekt manzilini yozing:",
        "Telefon raqamingiz:",
        "Taxminiy maydon (m²):",
        "Izoh yoki uy rasmini yuboring:"
    ]
}

THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi. Tez orada siz bilan bog'lanamiz."
}

# 🔹 Хранилище для шагов
user_data = {}

# --- Handlers ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    logger.info(f"Start from {chat_id} text={message.text} lang={message.from_user.language_code}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("RU", "UZ")
    bot.send_message(chat_id, "Выберите язык / Tilni tanlang:", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text in ["RU", "UZ"])
def choose_language(message):
    chat_id = message.chat.id
    lang = "ru" if message.text == "RU" else "uz"
    user_data[chat_id] = {"lang": lang, "step": 0, "answers": []}
    bot.send_message(chat_id, QUESTIONS[lang][0], reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Нажмите /start для начала")
        return

    user = user_data[chat_id]
    lang = user["lang"]

    # сохраняем ответ
    user["answers"].append(message.text)
    user["step"] += 1

    # если ещё есть вопросы
    if user["step"] < len(QUESTIONS[lang]):
        bot.send_message(chat_id, QUESTIONS[lang][user["step"]])
    else:
        try:
            name, address, phone, square, comment = user["answers"]

            if lang == "ru":
                text = (
                    f"📋 Новая заявка\n\n"
                    f"👤 Имя: {name}\n"
                    f"🏠 Адрес: {address}\n"
                    f"📞 Телефон: {phone}\n"
                    f"📐 Квадратура: {square}\n"
                    f"💬 Комментарий: {comment}"
                )
            else:
                text = (
                    f"📋 Yangi ariza\n\n"
                    f"👤 Ism: {name}\n"
                    f"🏠 Manzil: {address}\n"
                    f"📞 Telefon: {phone}\n"
                    f"📐 Maydon: {square}\n"
                    f"💬 Izoh: {comment}"
                )

            bot.send_message(GROUP_ID, text)  # в группу
            bot.send_message(chat_id, THANK_YOU[lang])  # пользователю
            del user_data[chat_id]  # очистить диалог
        except Exception as e:
            logger.error(f"Error sending to group: {e}")
            bot.send_message(chat_id, "❌ Ошибка при отправке заявки.")


# --- Flask routes ---

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
    app.run(host="0.0.0.0", port=PORT)








