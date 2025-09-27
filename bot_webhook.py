

# -*- coding: utf-8 -*-
import os
import json
import telebot
from flask import Flask, request

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "7592969962:AAE93nt3NRENC9LCxfomvONl7zqozS2SZh8")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "-4878488268")  # группа для заявок
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://zuhfacadebot-1.onrender.com/webhook")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

STATE = {}
DATA_FILE = "applications.json"

# Загрузка сохранённых заявок
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            STATE = json.load(f)
    except:
        STATE = {}

# Тексты на двух языках
TEXTS = {
    "ru": {
        "ask_name": "👋 Здравствуйте! Введите, пожалуйста, ваше имя:",
        "ask_phone": "📞 Укажите ваш номер телефона:",
        "ask_address": "📍 Укажите адрес объекта:",
        "ask_area": "📐 Укажите квадратуру объекта:",
        "ask_comment": "💬 Оставьте комментарий (например, вид фасадных работ):",
        "done": "✅ Спасибо! Ваша заявка принята. Мы скоро свяжемся с вами!",
    },
    "uz": {
        "ask_name": "👋 Assalomu alaykum! Iltimos, ismingizni kiriting:",
        "ask_phone": "📞 Telefon raqamingizni kiriting:",
        "ask_address": "📍 Ob’ekt manzilini kiriting:",
        "ask_area": "📐 Ob’ekt kvadraturasini kiriting:",
        "ask_comment": "💬 Izoh qoldiring (masalan, fasad ishlari turi):",
        "done": "✅ Rahmat! So‘rovingiz qabul qilindi. Tez orada siz bilan bog‘lanamiz!",
    }
}

QUESTIONS = ["name", "phone", "address", "area", "comment"]

# Сохранение заявок в файл
def save_state():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(STATE, f, ensure_ascii=False, indent=2)

# === Хэндлеры ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    lang = "ru"
    if message.text.startswith("/start uz"):
        lang = "uz"

    STATE[str(message.chat.id)] = {"step": "name", "lang": lang, "data": {}}
    save_state()
    bot.send_message(message.chat.id, TEXTS[lang]["ask_name"])

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    user_id = str(message.chat.id)

    if user_id not in STATE:
        bot.send_message(message.chat.id, "Напишите /start чтобы начать снова.")
        return

    step = STATE[user_id]["step"]
    lang = STATE[user_id]["lang"]

    # Сохраняем ответ
    STATE[user_id]["data"][step] = message.text

    # Переход к следующему шагу
    current_index = QUESTIONS.index(step)
    if current_index + 1 < len(QUESTIONS):
        next_step = QUESTIONS[current_index + 1]
        STATE[user_id]["step"] = next_step
        save_state()
        bot.send_message(message.chat.id, TEXTS[lang][f"ask_{next_step}"])
    else:
        # Все ответы собраны
        data = STATE[user_id]["data"]
        text = (
            f"📩 Новая заявка:\n\n"
            f"👤 Имя: {data.get('name')}\n"
            f"📞 Телефон: {data.get('phone')}\n"
            f"📍 Адрес: {data.get('address')}\n"
            f"📐 Квадратура: {data.get('area')}\n"
            f"💬 Комментарий: {data.get('comment')}"
        )
        bot.send_message(GROUP_CHAT_ID, text)
        bot.send_message(message.chat.id, TEXTS[lang]["done"])
        del STATE[user_id]
        save_state()

# === Flask routes ===
@app.route('/', methods=['GET'])
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









