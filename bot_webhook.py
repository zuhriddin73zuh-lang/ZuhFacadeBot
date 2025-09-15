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
GROUP_ID_RAW = os.getenv("GROUP_ID")  # ожидаем строку, содержащую -100...
STORAGE_FILE = os.getenv("APPLICATIONS_FILE", "applications.json")  # можно переопределить

if not TOKEN:
    log.error("TELEGRAM_TOKEN не задан. Установите переменную окружения TELEGRAM_TOKEN.")
    raise SystemExit(1)

if not GROUP_ID_RAW:
    log.error("GROUP_ID не задан. Установите переменную окружения GROUP_ID.")
    raise SystemExit(1)

try:
    GROUP_ID = int(GROUP_ID_RAW)
except ValueError:
    log.error("GROUP_ID должен быть числом (например -1001234567890). Текущее значение: %s", GROUP_ID_RAW)
    raise SystemExit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# -------- Состояния и данные в памяти --------
user_state = {}   # chat_id -> {"lang": "ru"/"uz", "step": int}
user_data = {}    # chat_id -> list of answers (index order)

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

applications = load_applications()  # dict app_id -> application dict

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
    """Извлекает языковой параметр из /start ..."""
    if not text:
        return None
    parts = text.split(maxsplit=1)
    param = ""
    if len(parts) > 1:
        param = parts[1].strip().lower()
    # возможные варианты: "go_uz", "go-uz", "uz", "ru", "start=uz"
    if param.startswith("start="):
        param = param.split("=", 1)[1]
    param = param.replace("-", "_")
    if param.startswith("go_"):
        param = param[3:]
    # нормализуем
    if param in ("uz", "uzbek", "o'zbek", "o‘zbek", "oz"):
        return "uz"
    if param in ("ru", "rus", "russian"):
        return "ru"
    return None

def is_valid_phone(s: str) -> bool:
    sdigits = "".join(ch for ch in s if ch.isdigit())
    return len(sdigits) >= 7  # минимальная проверка

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
        # По умолчанию русский, можно изменить
        lang = "ru"
    # Инициализация состояния
    user_state[chat_id] = {"lang": lang, "step": 0}
    user_data[chat_id] = []
    log.info("START from %s lang=%s", chat_id, lang)
    safe_send_message(chat_id, QUESTIONS[lang][0])

@bot.message_handler(func=lambda m: m.chat.id in user_state, content_types=['text', 'photo', 'document', 'sticker', 'video', 'audio'])
def handle_steps(message):
    chat_id = message.chat.id
    state = user_state.get(chat_id)
    if not state:
        return  # нечего делать

    lang = state["lang"]
    step = state["step"]
    q_count = len(QUESTIONS[lang])

    # Step 0..3 ожидают текст; step 4 (index 4) может быть любой тип (комментарий)
    if step < 4:
        # ожидаем текст
        if message.content_type != 'text':
            safe_send_message(chat_id, "⚠️ Пожалуйста, отвечайте текстом." if lang == "ru" else "⚠️ Iltimos, javobni matn ko'rinishida yuboring.")
            return
        text = message.text.strip()
        # валидации по шагам
        if step == 2:  # телефон
            if not is_valid_phone(text):
                safe_send_message(chat_id, "Пожалуйста, введите корректный номер телефона (минимум 7 цифр)." if lang == "ru" else "Iltimos, to'g'ri telefon raqamini kiriting (kamida 7 raqam).")
                return
        # сохранить ответ
        user_data[chat_id].append(text)
        state["step"] += 1
    else:
        # step == 4 — комментарий — принимаем любой тип
        if message.content_type == 'text':
            user_data[chat_id].append({"type": "text", "value": message.text.strip()})
        elif message.content_type == 'photo':
            # берем последний элемент списка photo (самое большое)
            file_id = message.photo[-1].file_id
            user_data[chat_id].append({"type": "photo", "file_id": file_id})
        elif message.content_type == 'document':
            file_id = message.document.file_id
            user_data[chat_id].append({"type": "document", "file_id": file_id, "file_name": getattr(message.document, 'file_name', None)})
        else:
            # другой тип — сохраняем как текстовую заметку
            user_data[chat_id].append({"type": message.content_type, "value": "<non-text data>"})
        state["step"] += 1

    # следующий шаг или завершение
    if state["step"] < q_count:
        # отправляем следующий вопрос
        safe_send_message(chat_id, QUESTIONS[lang][state["step"]])
    else:
        # собрали все ответы
        answers = user_data.get(chat_id, [])
        # answers expected: name (0), address (1), phone (2), square (3), comment (4)
        # проверяем обязательные поля: адрес и телефон
        name = answers[0] if len(answers) > 0 else ""
        address = answers[1] if len(answers) > 1 else ""
        phone = answers[2] if len(answers) > 2 else ""
        square = answers[3] if len(answers) > 3 else ""
        comment = answers[4] if len(answers) > 4 else {"type": "text", "value": ""}

        if not address or not phone:
            # переспрашиваем обязательные поля — отправляем соответствующий вопрос
            if not address:
                state["step"] = 1
                safe_send_message(chat_id, QUESTIONS[lang][1])
                return
            if not phone:
                state["step"] = 2
                safe_send_message(chat_id, QUESTIONS[lang][2])
                return

        # Формируем текст заявки (на выбранном языке)
        if lang == "ru":
            app_text = (
                f"📩 Новая заявка\n\n"
                f"👤 Имя: {name}\n"
                f"🏠 Адрес: {address}\n"
                f"📞 Телефон: {phone}\n"
                f"📐 Квадратов: {square}\n"
            )
            # комментарий будет отдельно (текст или медиа)
            user_thanks = THANK_YOU["ru"]
        else:
            app_text = (
                f"📩 Yangi ariza\n\n"
                f"👤 Ism: {name}\n"
                f"🏠 Manzil: {address}\n"
                f"📞 Telefon: {phone}\n"
                f"📐 Kvadrat: {square}\n"
            )
            user_thanks = THANK_YOU["uz"]

        # Отправляем в группу: если комментарий — фото, отправляем фото с подписью
        try:
            if isinstance(comment, dict) and comment.get("type") == "photo":
                file_id = comment.get("file_id")
                # отправим фото в группу с подписью
                bot.send_photo(GROUP_ID, file_id, caption=app_text)
            elif isinstance(comment, dict) and comment.get("type") == "document":
                file_id = comment.get("file_id")
                fn = comment.get("file_name") or ""
                caption = app_text + ("\nФайл: " + fn if fn else "")
                bot.send_document(GROUP_ID, file_id, caption=caption)
            else:
                # текстовый комментарий или отсутствует
                comment_text = comment.get("value") if isinstance(comment, dict) else ""
                full_text = app_text + ("\n💬 Комментарий: " + comment_text if comment_text else "")
                bot.send_message(GROUP_ID, full_text)
        except Exception as e:
            log.exception("Ошибка отправки заявки в группу: %s", e)
            # попытаемся отправить хотя бы текст
            try:
                bot.send_message(GROUP_ID, app_text)
            except Exception:
                log.exception("Ошибка при fallback отправке в группу")

        # Сохраняем в файл
        store_application(chat_id, lang, [name, address, phone, square, comment if isinstance(comment, dict) else {"type":"text","value":comment}])

        # Благодарим пользователя
        safe_send_message(chat_id, user_thanks)

        # очистка состояния
        user_state.pop(chat_id, None)
        user_data.pop(chat_id, None)

# -------- Webhook (Flask) --------
@app.route("/webhook", methods=["POST"])
def webhook():
    # логируем сырой JSON для отладки (можно отключить)
    raw = request.get_data().decode("utf-8")
    log.debug("WEBHOOK RAW: %s", raw[:1000])  # не перегружаем лог при больших данных
    try:
        update = telebot.types.Update.de_json(raw)
    except Exception as e:
        log.exception("Ошибка парсинга update: %s", e)
        return "bad request", 400
    try:
        bot.process_new_updates([update])
    except Exception as e:
        log.exception("Ошибка process_new_updates: %s", e)
        return "error", 500
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

if __name__ == "__main__":
    # при локальном запуске (не на Render) можно запустить так:
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



   

           
        









