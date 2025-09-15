# -*- coding: utf-8 -*-
import os
import time
import json
import logging
import sqlite3
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
GROUP_ID_RAW = os.getenv("GROUP_ID", "-1094323262")  # временно ваш ID
STORAGE_FILE = os.getenv("APPLICATIONS_FILE", "applications.json")

if not TOKEN:
    log.error("TELEGRAM_TOKEN не задан.")
    raise SystemExit(1)

try:
    GROUP_ID = int(GROUP_ID_RAW)
except ValueError:
    log.error("GROUP_ID должен быть числом. Текущее значение: %s", GROUP_ID_RAW)
    raise SystemExit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# -------- База данных SQLite --------
DB_FILE = "bot_database.db"

def init_database():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Таблица для состояний пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_states (
        chat_id INTEGER PRIMARY KEY,
        lang TEXT NOT NULL,
        step INTEGER NOT NULL,
        answers TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица для заявок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id TEXT PRIMARY KEY,
        chat_id INTEGER NOT NULL,
        lang TEXT NOT NULL,
        answers TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()

def get_user_state(chat_id):
    """Получить состояние пользователя из БД"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT lang, step, answers FROM user_states WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        lang, step, answers_json = result
        return {
            "lang": lang,
            "step": step,
            "answers": json.loads(answers_json) if answers_json else []
        }
    return None

def save_user_state(chat_id, lang, step, answers):
    """Сохранить состояние пользователя в БД"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    answers_json = json.dumps(answers, ensure_ascii=False)
    
    cursor.execute('''
    INSERT OR REPLACE INTO user_states (chat_id, lang, step, answers)
    VALUES (?, ?, ?, ?)
    ''', (chat_id, lang, step, answers_json))
    
    conn.commit()
    conn.close()

def delete_user_state(chat_id):
    """Удалить состояние пользователя из БД"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_states WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

# Инициализируем БД при запуске
init_database()

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

# -------- Хранилище заявок --------
def store_application(chat_id: int, lang: str, answers: list):
    app_id = f"{chat_id}_{int(time.time())}"
    entry = {
        "id": app_id,
        "chat_id": chat_id,
        "lang": lang,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "answers": answers
    }
    
    # Сохраняем в SQLite
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO applications (id, chat_id, lang, answers, timestamp)
    VALUES (?, ?, ?, ?, ?)
    ''', (app_id, chat_id, lang, json.dumps(answers, ensure_ascii=False), entry['timestamp']))
    conn.commit()
    conn.close()
    
    # Также сохраняем в JSON файл для резерва
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        data[app_id] = entry
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.exception("Ошибка записи в файл: %s", e)
    
    return app_id

# -------- Утилиты --------
def parse_start_param(text: str) -> Optional[str]:
    if not text:
        return None
    parts = text.split(maxsplit=1)
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
    return "ru"  # по умолчанию русский

def is_valid_phone(s: str) -> bool:
    sdigits = "".join(ch for ch in s if ch.isdigit())
    return len(sdigits) >= 7

def safe_send_message(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        log.exception("Ошибка отправки сообщения: %s", e)

# -------- Обработчики --------
@bot.message_handler(commands=['start', 'get_id'])
def handle_start(message):
    chat_id = message.chat.id
    
    if message.text == '/get_id':
        bot.send_message(chat_id, f"🆔 ID этого чата: `{chat_id}`", parse_mode='Markdown')
        return
        
    text = message.text or ""
    lang = parse_start_param(text)
    
    # Сохраняем состояние в БД
    save_user_state(chat_id, lang, 0, [])
    
    log.info("START from %s lang=%s", chat_id, lang)
    safe_send_message(chat_id, QUESTIONS[lang][0])

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'document'])
def handle_all_messages(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)
    
    if not state:
        return  # пользователь не начал диалог
        
    lang = state["lang"]
    step = state["step"]
    answers = state["answers"]
    q_count = len(QUESTIONS[lang])

    # Обработка шагов
    if step < 3:  # Имя, адрес, телефон
        if message.content_type != 'text':
            safe_send_message(chat_id, "⚠️ Пожалуйста, отвечайте текстом." if lang == "ru" else "⚠️ Iltimos, javobni matn ko'rinishida yuboring.")
            return
            
        text = message.text.strip()
        if step == 2 and not is_valid_phone(text):
            safe_send_message(chat_id, "Пожалуйста, введите корректный номер телефона." if lang == "ru" else "Iltimos, to'g'ri telefon raqamini kiriting.")
            return
            
        answers.append(text)
        step += 1
        
    elif step == 3:  # Площадь
        if message.content_type != 'text':
            safe_send_message(chat_id, "⚠️ Пожалуйста, укажите площадь числом." if lang == "ru" else "⚠️ Iltimos, maydonni raqamda yuboring.")
            return
            
        answers.append(message.text.strip())
        step += 1
        
    elif step == 4:  # Комментарий
        if message.content_type == 'text':
            answers.append({"type": "text", "value": message.text.strip()})
        elif message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            answers.append({"type": "photo", "file_id": file_id})
        elif message.content_type == 'document':
            file_id = message.document.file_id
            answers.append({"type": "document", "file_id": file_id})
        else:
            answers.append({"type": message.content_type, "value": "данные"})
        step += 1
        
    else:
        delete_user_state(chat_id)
        return

    # Сохраняем обновленное состояние
    save_user_state(chat_id, lang, step, answers)

    # Отправляем следующий вопрос или завершаем
    if step < q_count:
        safe_send_message(chat_id, QUESTIONS[lang][step])
    else:
        # Все ответы получены
        name, address, phone, square, comment = answers[0], answers[1], answers[2], answers[3], answers[4]
        
        if lang == "ru":
            app_text = f"📩 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратов: {square}"
            user_thanks = THANK_YOU["ru"]
        else:
            app_text = f"📩 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Kvadrat: {square}"
            user_thanks = THANK_YOU["uz"]
            
        # Отправляем в группу
        try:
            if isinstance(comment, dict) and comment.get("type") == "photo":
                bot.send_photo(GROUP_ID, comment["file_id"], caption=app_text)
            elif isinstance(comment, dict) and comment.get("type") == "document":
                bot.send_document(GROUP_ID, comment["file_id"], caption=app_text)
            else:
                comment_text = comment.get("value", "") if isinstance(comment, dict) else str(comment)
                full_text = app_text + f"\n💬 Комментарий: {comment_text}" if lang == "ru" else f"\n💬 Izoh: {comment_text}"
                bot.send_message(GROUP_ID, full_text)
        except Exception as e:
            log.error("Ошибка отправки в группу: %s", e)
            bot.send_message(GROUP_ID, app_text)
            
        # Сохраняем и очищаем
        store_application(chat_id, lang, answers)
        safe_send_message(chat_id, user_thanks)
        delete_user_state(chat_id)

# -------- Webhook --------
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    abort(403)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running. Webhook: /webhook", 200

if __name__ == "__main__":
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url="https://zuhfacadebot-1.onrender.com/webhook")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
