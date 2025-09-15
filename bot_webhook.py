# -*- coding: utf-8 -*-
import os
import time
import json
import logging
from datetime import datetime
from typing import Optional

import telebot
from telebot import types
from flask import Flask, request, abort

# -------- Настройки логирования --------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# -------- Переменные окружения (Render) --------
TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID_RAW = os.getenv("GROUP_ID") 
STORAGE_FILE = os.getenv("APPLICATIONS_FILE", "applications.json")

if not TOKEN:
    log.error("TELEGRAM_TOKEN не задан.")
    raise SystemExit(1)

if not GROUP_ID_RAW:
    log.error("GROUP_ID не задан.")
    raise SystemExit(1)

try:
    GROUP_ID = int(GROUP_ID_RAW)
except ValueError:
    log.error("GROUP_ID должен быть числом. Текущее значение: %s", GROUP_ID_RAW)
    raise SystemExit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# -------- Состояния и данные в памяти --------
user_state = {}   
user_data = {}    

# -------- Вопросы и ответы --------
QUESTIONS = {
    "ru": [
        "Здравствуйте! Пожалуйста, укажите ваше имя:",
        "Укажите адрес (улица, дом/кв):",
        "Ваш номер телефона (обязательно):",
        "Сколько квадратов? (пример: 120 или 120.5):",
        "Оставьте комментарий (текст или фото):"
    ],
    "uz": [
        "Assalomu alaykum! Iltimos, ismingizni kiriting:",
        "Manzilingizni yozing (ko'cha, uy/xona):",
        "Telefon raqamingiz (majburiy):",
        "Necha kvadrat? (masalan: 120 yoki 120.5):",
        "Izohni qoldiring (matn yoki rasm):"
    ]
}

THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята, мы вам скоро позвоним.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi, tez orada sizga qo'ng'iroq qilamiz."
}

# -------- Хранилище заявок (файл) --------
def load_applications():
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        log.exception("Ошибка чтения storage file: %s", e)
        return {}

def save_applications(data):
    try:
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.exception("Ошибка записи storage file: %s", e)

applications = load_applications()

def store_application(chat_id: int, lang: str, answers: list):
    app_id = f"{chat_id}_{int(time.time())}"
    entry = {
        "id": app_id,
        "chat_id": chat_id,
        "lang": lang,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "answers": answers
    }
    applications[app_id] = entry
    save_applications(applications)
    return app_id

# -------- Утилиты --------
def parse_start_param(text: str) -> Optional[str]:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    param = ""
    if len(parts) > 1:
        param = parts[1].strip().lower()
    if param.startswith("start="):
        param = param.split("=", 1)[1]
    param = param.replace("-", "_")
    if param.startswith("go_"):
        param = param[3:]
    if param in ("uz", "uzbek", "o'zbek", "o‘zbek", "oz"):
        return "uz"
    if param in ("ru", "rus", "russian"):
        return "ru"
    return None

def is_valid_phone(s: str) -> bool:
    sdigits = "".join(ch for ch in s if ch.isdigit())
    return len(sdigits) >= 7

def safe_send_message(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        log.exception("Ошибка при отправке сообщения %s: %s", chat_id, e)

# -------- Обработчики --------
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    text = message.text or ""
    lang = parse_start_param(text)
    if lang is None:
        lang = "ru"
    user_state[chat_id] = {"lang": lang, "step": 0}
    user_data[chat_id] = []
    log.info("START from %s lang=%s", chat_id, lang)
    safe_send_message(chat_id, QUESTIONS[lang][0])

# 🔥 ДОБАВЛЕНО: Команда для получения ID канала
@bot.message_handler(commands=['get_id'])
def get_chat_id_command(message):
    """Простая команда для получения ID любого чата"""
    chat_id = message.chat.id
    bot.send_message(message.chat.id, f"📋 ID этого чата: `{chat_id}`", parse_mode='MarkdownV2')

@bot.message_handler(func=lambda m: m.chat.id in user_state, content_types=['text', 'photo', 'document', 'sticker', 'video', 'audio'])
def handle_steps(message):
    chat_id = message.chat.id
    state = user_state.get(chat_id)
    if not state:
        return

    lang = state["lang"]
    step = state["step"]
    q_count = len(QUESTIONS[lang])

    if step < 3:
        if message.content_type != 'text':
            safe_send_message(chat_id, "⚠️ Пожалуйста, отвечайте текстом." if lang == "ru" else "⚠️ Iltimos, javobni matn ko'rinishida yuboring.")
            return
        text = message.text.strip()
        if step == 2 and not is_valid_phone(text):
            safe_send_message(chat_id, "Пожалуйста, введите корректный номер телефона (минимум 7 цифр)." if lang == "ru" else "Iltimos, to'g'ri telefon raqamini kiriting (kamida 7 raqam).")
            return
        user_data[chat_id].append(text)
        state["step"] += 1
    elif step == 3:
        if message.content_type != 'text':
            safe_send_message(chat_id, "⚠️ Пожалуйста, укажите площадь числом." if lang == "ru" else "⚠️ Iltimos, maydonni raqamda yuboring.")
            return
        user_data[chat_id].append(message.text.strip())
        state["step"] += 1
        safe_send_message(chat_id, QUESTIONS[lang][4])
        return
    elif step == 4:
        if message.content_type == 'text':
            user_data[chat_id].append({"type": "text", "value": message.text.strip()})
        elif message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            user_data[chat_id].append({"type": "photo", "file_id": file_id})
        elif message.content_type == 'document':
            file_id = message.document.file_id
            user_data[chat_id].append({"type": "document", "file_id": file_id, "file_name": getattr(message.document, 'file_name', None)})
        else:
            user_data[chat_id].append({"type": message.content_type, "value": "<non-text data>"})
        state["step"] += 1
    else:
        user_state.pop(chat_id, None)
        user_data.pop(chat_id, None)
        return

    if state["step"] == 4:
        safe_send_message(chat_id, QUESTIONS[lang][4])
        return

    if state["step"] == 5:
        answers = user_data.get(chat_id, [])
        if len(answers) < 5:
            safe_send_message(chat_id, "Что-то пошло не так. Пожалуйста, начните снова с /start." if lang == "ru" else "Nimadir noto'g'ri ketdi. Iltimos, /start buyrug'i bilan qayta boshlang.")
            user_state.pop(chat_id, None)
            user_data.pop(chat_id, None)
            return

        name, address, phone, square, comment = answers[0], answers[1], answers[2], answers[3], answers[4]

        if lang == "ru":
            app_text = (f"📩 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратов: {square}\n")
            user_thanks = THANK_YOU["ru"]
        else:
            app_text = (f"📩 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Kvadrat: {square}\n")
            user_thanks = THANK_YOU["uz"]

        try:
            if isinstance(comment, dict) and comment.get("type") == "photo":
                file_id = comment.get("file_id")
                bot.send_photo(GROUP_ID, file_id, caption=app_text)
            elif isinstance(comment, dict) and comment.get("type") == "document":
                file_id = comment.get("file_id")
                fn = comment.get("file_name") or ""
                caption = app_text + (f"\nФайл: {fn}" if lang == "ru" else f"\nFayl: {fn}")
                bot.send_document(GROUP_ID, file_id, caption=caption)
            else:
                comment_text = comment.get("value") if isinstance(comment, dict) else str(comment)
                comment_label = "\n💬 Комментарий: " if lang == "ru" else "\n💬 Izoh: "
                full_text = app_text + (comment_label + comment_text if comment_text else "")
                bot.send_message(GROUP_ID, full_text)
        except Exception as e:
            log.exception("Ошибка отправки заявки в группу: %s", e)
            try:
                bot.send_message(GROUP_ID, app_text + "\n[Не удалось отправить вложение]")
            except Exception:
                log.exception("Ошибка при fallback отправке в группу")

        store_application(chat_id, lang, answers)
        safe_send_message(chat_id, user_thanks)
        user_state.pop(chat_id, None)
        user_data.pop(chat_id, None)

# -------- Webhook (Flask) --------
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running. Set webhook to /webhook", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://zuhfacadebot-1.onrender.com/webhook")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
