# bot_webhook.py
import os
import json
import logging
import threading
from flask import Flask, request
import telebot
from telebot import types

# ========== НАСТРОЙКИ: замените на свои =============
TOKEN = os.environ.get("TOKEN") or "YOUR_TOKEN_HERE"
GROUP_ID = int(os.environ.get("GROUP_ID") or "YOUR_GROUP_ID_HERE")  # например: -4878488268
USER_DATA_FILE = "user_data.json"
PORT = int(os.environ.get("PORT", 5000))
# ====================================================

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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

# потокобезопасный доступ к файлу состояния
file_lock = threading.Lock()
user_data = {}

def load_user_data():
    global user_data
    if os.path.exists(USER_DATA_FILE):
        try:
            with file_lock, open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # ключи в JSON будут строками, приведём к int
            user_data = {int(k): v for k, v in data.items()}
            logger.info("Loaded user_data from file")
        except Exception as e:
            logger.exception("Failed to load user_data: %s", e)
            user_data = {}
    else:
        user_data = {}

def save_user_data():
    try:
        with file_lock, open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            # привести ключи к строкам для JSON
            json.dump({str(k): v for k, v in user_data.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("Failed to save user_data: %s", e)

load_user_data()

# ---------- ХЕЛПЕРЫ ----------
def detect_lang_from_start_text(text, from_user_langcode):
    if not text:
        text = ""
    parts = text.strip().split()
    if len(parts) > 1:
        payload = parts[1].lower()
        if payload.startswith("uz"):
            return "uz"
        if payload.startswith("ru"):
            return "ru"
    # fallback: используем language_code от Telegram
    if from_user_langcode:
        lc = from_user_langcode.lower()
        if lc.startswith("uz"):
            return "uz"
        if lc.startswith("ru"):
            return "ru"
    return None

def set_user_start(chat_id, lang):
    user_data[chat_id] = {"lang": lang, "step": 0, "answers": []}
    save_user_data()

# ---------- Обработчики ----------
@bot.message_handler(commands=["start"])
def handle_start(message):
    try:
        chat_id = message.chat.id
        logger.info("Start from %s text=%s language_code=%s", chat_id, message.text, message.from_user.language_code)
        lang = detect_lang_from_start_text(message.text, message.from_user.language_code)
        if lang:
            set_user_start(chat_id, lang)
            bot.send_message(chat_id, QUESTIONS[lang][0])
            return
        # Если язык не определён — предложим выбор (one_time_keyboard)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("RU", "UZ")
        bot.send_message(chat_id, "Выберите язык / Tilni tanlang:", reply_markup=markup)
    except Exception as e:
        logger.exception("Error in handle_start: %s", e)

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().upper() in ["RU", "UZ", "РУС", "UZB"])
def choose_lang_keyboard(message):
    try:
        chat_id = message.chat.id
        # если уже в разговоре — игнорируем как языковую кнопку
        if chat_id in user_data and user_data[chat_id].get("step", 0) > 0:
            return
        txt = message.text.strip().upper()
        lang = "uz" if txt.startswith("U") else "ru"
        set_user_start(chat_id, lang)
        bot.send_message(chat_id, QUESTIONS[lang][0], reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        logger.exception("Error in choose_lang_keyboard: %s", e)

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    try:
        chat_id = message.chat.id
        if chat_id not in user_data:
            bot.send_message(chat_id, "Нажмите /start для начала заявки")
            return

        user = user_data[chat_id]
        lang = user["lang"]
        step = user["step"]

        # сохраним ответ (текст или ссылку на файл)
        if message.content_type == "text":
            answer = message.text
        elif message.content_type == "photo":
            # берем самый большой
            file_id = message.photo[-1].file_id
            answer = {"type": "photo", "file_id": file_id}
        elif message.content_type == "document":
            answer = {"type": "document", "file_id": message.document.file_id, "file_name": message.document.file_name}
        else:
            answer = str(message.content_type)

        user["answers"].append(answer)
        user["step"] = step + 1
        save_user_data()

        # следующий вопрос или финал
        if user["step"] < len(QUESTIONS[lang]):
            bot.send_message(chat_id, QUESTIONS[lang][user["step"]])
            return

        # финал: собираем текст заявки и отправляем в группу
        answers = user["answers"]
        # нормализуем текстовые поля
        def text_or_empty(i):
            return answers[i] if i < len(answers) and isinstance(answers[i], str) else ""

        name = text_or_empty(0)
        address = text_or_empty(1)
        phone = text_or_empty(2)
        square = text_or_empty(3)
        comment = text_or_empty(4)

        if lang == "ru":
            text = f"📋 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратура: {square}\n💬 Комментарий: {comment}"
            thank = THANK_YOU["ru"]
        else:
            text = f"📋 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Maydon: {square}\n💬 Izoh: {comment}"
            thank = THANK_YOU["uz"]

        bot.send_message(GROUP_ID, text)

        # пересылаем файлы (если были)
        for ans in answers:
            if isinstance(ans, dict) and ans.get("type") == "photo":
                try:
                    bot.send_photo(GROUP_ID, ans["file_id"])
                except Exception:
                    logger.exception("Failed to forward photo")
            if isinstance(ans, dict) and ans.get("type") == "document":
                try:
                    bot.send_document(GROUP_ID, ans["file_id"])
                except Exception:
                    logger.exception("Failed to forward document")

        bot.send_message(chat_id, thank)
        # очистка состояния
        del user_data[chat_id]
        save_user_data()

    except Exception as e:
        logger.exception("Error in handle_all_messages: %s", e)
        try:
            bot.send_message(message.chat.id, "Произошла ошибка, повторите /start")
        except Exception:
            pass

# ---------- webhook endpoint ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)
        return "Error", 500

@app.route("/")
def index():
    return "✅ Bot is running!"

if __name__ == "__main__":
    logger.info("Starting Flask app on port %s", PORT)
    app.run(host="0.0.0.0", port=PORT)






