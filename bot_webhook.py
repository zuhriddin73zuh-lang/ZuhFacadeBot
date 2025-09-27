# -*- coding: utf-8 -*-
import os
import json
import logging
import telebot
from flask import Flask, request

# ========== Настройки (ENV) ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "7592969962:AAE93nt3NRENC9LCxfomvONl7zqozS2SZh8")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-4878488268"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://zuhfacadebot-1.onrender.com/webhook")
PORT = int(os.getenv("PORT", 10000))

# ========== Логирование ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========== Инициализация ==========
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

SESSIONS_FILE = "sessions.json"        # незавершённые диалоги / прогресс
APPLICATIONS_FILE = "applications.json"  # все завершённые заявки

# загрузка сессий
def load_sessions():
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.exception("load_sessions failed: %s", e)
    return {}

def save_sessions(sessions):
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("save_sessions failed: %s", e)

def append_application(app):
    try:
        apps = []
        if os.path.exists(APPLICATIONS_FILE):
            with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                apps = json.load(f)
        apps.append(app)
        with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("append_application failed: %s", e)

# Сессии: ключи — строки chat_id
sessions = load_sessions()

# ========== Тексты (вежливо) ==========
TEXTS = {
    "ru": {
        "ask_name": "👋 Здравствуйте! Пожалуйста, укажите ваше имя.",
        "ask_phone": "Спасибо! Напишите, пожалуйста, ваш номер телефона.",
        "ask_address": "Отлично. Укажите, пожалуйста, адрес объекта.",
        "ask_area": "Хорошо. Примерная квадратура объекта (в м²), пожалуйста.",
        "ask_comment": "Спасибо — добавьте, пожалуйста, комментарий или пожелания.",
        "ask_photo": "Если хотите, прикрепите фото объекта (это необязательно). Или напишите «пропустить».",
        "done": "✅ Спасибо! Ваша заявка принята. Мы скоро свяжемся с вами.",
    },
    "uz": {
        "ask_name": "👋 Assalomu alaykum! Iltimos, ismingizni kiriting.",
        "ask_phone": "Rahmat! Iltimos, telefon raqamingizni yozing.",
        "ask_address": "Zo'r. Iltimos, ob’ekt manzilini kiriting.",
        "ask_area": "Maydonni (m²) taxminiy yozing, iltimos.",
        "ask_comment": "Rahmat — izoh yoki istaklaringizni yozing.",
        "ask_photo": "Agar hohlasangiz, ob’ekt rasmini yuboring (ixtiyoriy). Yoki «o‘tkazib yuborish» deb yozing.",
        "done": "✅ Rahmat! So‘rovingiz qabul qilindi. Tez orada siz bilan bog‘lanamiz.",
    }
}

# порядок шагов
STEPS = ["name", "phone", "address", "area", "comment", "photo"]

# ========= Хэндлеры ==========
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = str(message.chat.id)
    text = (message.text or "").strip()
    # deep-link: /start uz  или /start ru
    lang = "ru"
    parts = text.split()
    if len(parts) > 1 and parts[1].lower() in ("uz", "ru"):
        lang = parts[1].lower()
    # инициализация сессии
    sessions[chat_id] = {
        "step": "name",
        "lang": lang,
        "data": {},
        "photos": []  # список file_id
    }
    save_sessions(sessions)
    bot.send_message(int(chat_id), TEXTS[lang]["ask_name"])

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'document'])
def handle_all(message):
    chat_id = str(message.chat.id)
    if chat_id not in sessions:
        bot.send_message(message.chat.id, "Напишите /start, чтобы начать заявку.")
        return

    session = sessions[chat_id]
    step = session.get("step")
    lang = session.get("lang", "ru")

    # если получили фото на любом шаге и текущий шаг — photo, записываем
    if message.content_type == "photo":
        # сохраняем file_id самого большого фото
        file_id = message.photo[-1].file_id
        session.setdefault("photos", []).append(file_id)
        # если сейчас шаг photo — считаем фото добавленным и завершаем
        if step == "photo":
            # finalize
            finalize_application(chat_id)
            return
        else:
            # если фото прислали не на шаге фото, просто подтвердим и ждём следующий ответ
            bot.send_message(message.chat.id, TEXTS[lang]["ask_" + step])
            save_sessions(sessions)
            return

    if message.content_type == "document":
        # сохраняем документы как file_id
        file_id = message.document.file_id
        session.setdefault("photos", []).append({"doc": file_id})
        if step == "photo":
            finalize_application(chat_id)
            return
        else:
            bot.send_message(message.chat.id, TEXTS[lang]["ask_" + step])
            save_sessions(sessions)
            return

    # текстовые ответы:
    text = (message.text or "").strip()

    # если на шаге фото пользователь написал "пропустить" / "o‘tkazib" — считаем пропуском
    if step == "photo" and text.lower() in ("пропустить", "пропусти", "skip", "o'tkazib", "o‘tkazib", "o' tkazib", "o`tkazib"):
        finalize_application(chat_id)
        return

    # сохраняем ответ под текущим ключом
    session["data"][step] = text
    # двигаем шаг
    try:
        idx = STEPS.index(step)
    except ValueError:
        # на всякий случай — переинициализируем
        session["step"] = "name"
        save_sessions(sessions)
        bot.send_message(message.chat.id, TEXTS[lang]["ask_name"])
        return

    # следующий шаг или финал
    if idx + 1 < len(STEPS):
        next_step = STEPS[idx + 1]
        session["step"] = next_step
        save_sessions(sessions)
        # если следующий шаг — photo, специальный текст
        bot.send_message(message.chat.id, TEXTS[lang].get(f"ask_{next_step}", TEXTS[lang]["ask_comment"]))
    else:
        # все поля собраны — финализируем
        finalize_application(chat_id)

def finalize_application(chat_id_str):
    session = sessions.get(chat_id_str)
    if not session:
        return
    lang = session.get("lang", "ru")
    data = session.get("data", {})
    photos = session.get("photos", [])

    # формируем текст заявки по языку
    if lang == "uz":
        app_text = (
            f"📩 Yangi so‘rov:\n\n"
            f"👤 Ism: {data.get('name','')}\n"
            f"📞 Telefon raqami: {data.get('phone','')}\n"
            f"📍 Manzil: {data.get('address','')}\n"
            f"📐 Maydon: {data.get('area','')} m²\n"
            f"💬 Izoh: {data.get('comment','')}"
        )
    else:
        app_text = (
            f"📩 Новая заявка:\n\n"
            f"👤 Имя: {data.get('name','')}\n"
            f"📞 Телефон: {data.get('phone','')}\n"
            f"📍 Адрес: {data.get('address','')}\n"
            f"📐 Квадратура: {data.get('area','')} м²\n"
            f"💬 Комментарий: {data.get('comment','')}"
        )

    # отправляем в группу
    try:
        bot.send_message(GROUP_CHAT_ID, app_text)
        # пересылаем фото/документы, если есть
        for p in photos:
            try:
                if isinstance(p, dict) and p.get("doc"):
                    bot.send_document(GROUP_CHAT_ID, p["doc"])
                else:
                    bot.send_photo(GROUP_CHAT_ID, p)
            except Exception:
                logger.exception("Failed to forward media to group")
    except Exception:
        logger.exception("Failed to send application to group")

    # сохраняем заявку локально
    app_record = {
        "chat_id": int(chat_id_str),
        "lang": lang,
        "data": data,
        "photos": photos
    }
    append_application(app_record)

    # отвечаем пользователю
    try:
        bot.send_message(int(chat_id_str), TEXTS[lang]["done"])
    except Exception:
        logger.exception("Failed to send confirmation to user")

    # удаляем сессию и сохраняем
    sessions.pop(chat_id_str, None)
    save_sessions(sessions)

# ========== Flask endpoints ==========
@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception:
        logger.exception("Webhook processing error")
    return "OK", 200

# при старте ставим webhook
with app.app_context():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info("Webhook set to %s", WEBHOOK_URL)
    except Exception:
        logger.exception("Failed to set webhook")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
