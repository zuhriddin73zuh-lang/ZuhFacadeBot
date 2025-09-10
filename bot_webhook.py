# -*- coding: utf-8 -*-
import os
import telebot
from telebot import types
from flask import Flask, request
from datetime import datetime, timedelta, timezone

# -----------------------------
# Безопасный токен и ID группы для Render / локального теста
TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))
# -----------------------------

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

STATE = {}

TXT = {
    "choose_lang": "Выберите язык / Tilni tanlang:",
    "ru": {
        "ask_name": "Введите ваше имя:",
        "ask_phone": "Введите ваш номер телефона:",
        "ask_addr": "Введите адрес объекта:",
        "ask_area": "Введите примерную площадь фасада (м²):",
        "ask_comment": "Комментарий (необязательно):",
        "done": "✅ Спасибо! Ваша заявка принята. Мы свяжемся с вами.",
    },
    "uz": {
        "ask_name": "Ismingizni kiriting:",
        "ask_phone": "Telefon raqamingizni kiriting:",
        "ask_addr": "Obyekt manzilini kiriting:",
        "ask_area": "Fasadning taxminiy maydoni (m²):",
        "ask_comment": "Izoh (majburiy emas):",
        "done": "✅ Rahmat! So‘rovingiz qabul qilindi. Tez orada siz bilan bog‘lanamiz.",
    },
}

def tz_now():
    tz = timezone(timedelta(hours=5))  # Ташкент
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")

def lang_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("Русский", "O‘zbekcha")
    return kb

# ---------------- Диалог -----------------
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def any_message(message):
    uid = message.from_user.id
    if uid not in STATE:
        bot.send_message(message.chat.id, TXT["choose_lang"], reply_markup=lang_kb())
        bot.register_next_step_handler(message, choose_lang)

def choose_lang(message):
    text = (message.text or "").strip()
    if text == "Русский":
        lang = "ru"
    elif text == "O‘zbekcha":
        lang = "uz"
    else:
        bot.send_message(message.chat.id, TXT["choose_lang"], reply_markup=lang_kb())
        bot.register_next_step_handler(message, choose_lang)
        return

    STATE[message.from_user.id] = {"lang": lang}
    bot.send_message(message.chat.id, TXT[lang]["ask_name"], reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_phone)

def ask_phone(message):
    uid = message.from_user.id
    st = STATE.get(uid, {})
    lang = st.get("lang", "ru")
    name = (message.text or "").strip()
    if not name:
        bot.send_message(message.chat.id, TXT[lang]["ask_name"])
        bot.register_next_step_handler(message, ask_phone)
        return
    st["name"] = name
    STATE[uid] = st
    bot.send_message(message.chat.id, TXT[lang]["ask_phone"])
    bot.register_next_step_handler(message, ask_addr)

def ask_addr(message):
    uid = message.from_user.id
    st = STATE.get(uid, {})
    lang = st.get("lang", "ru")
    phone = (message.text or "").strip()
    if not phone:
        bot.send_message(message.chat.id, TXT[lang]["ask_phone"])
        bot.register_next_step_handler(message, ask_addr)
        return
    st["phone"] = phone
    STATE[uid] = st
    bot.send_message(message.chat.id, TXT[lang]["ask_addr"])
    bot.register_next_step_handler(message, ask_area)

def ask_area(message):
    uid = message.from_user.id
    st = STATE.get(uid, {})
    lang = st.get("lang", "ru")
    addr = (message.text or "").strip()
    if not addr:
        bot.send_message(message.chat.id, TXT[lang]["ask_addr"])
        bot.register_next_step_handler(message, ask_area)
        return
    st["addr"] = addr
    STATE[uid] = st
    bot.send_message(message.chat.id, TXT[lang]["ask_area"])
    bot.register_next_step_handler(message, ask_comment)

def ask_comment(message):
    uid = message.from_user.id
    st = STATE.get(uid, {})
    lang = st.get("lang", "ru")
    area = (message.text or "").strip()
    if not area:
        bot.send_message(message.chat.id, TXT[lang]["ask_area"])
        bot.register_next_step_handler(message, ask_comment)
        return
    st["area"] = area
    STATE[uid] = st
    bot.send_message(message.chat.id, TXT[lang]["ask_comment"])
    bot.register_next_step_handler(message, finish_request)

def finish_request(message):
    uid = message.from_user.id
    st = STATE.get(uid, {})
    lang = st.get("lang", "ru")
    comment = (message.text or "").strip()
    st["comment"] = comment if comment else "—"
    STATE[uid] = st

    name = st.get("name", "—")
    phone = st.get("phone", "—")
    addr = st.get("addr", "—")
    area = st.get("area", "—")
    comment = st.get("comment", "—")

    bot.send_message(message.chat.id, TXT[lang]["done"])

    text = (
        f"📌 Новая заявка\n\n"
        f"👤 Имя: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🏠 Адрес: {addr}\n"
        f"📐 Площадь: {area}\n"
        f"💬 Комментарий: {comment}\n"
        f"⏰ Время: {tz_now()}"
    )
    bot.send_message(GROUP_ID, text)
    STATE.pop(uid, None)

# --------- Flask webhook ---------
@app.route(f"/webhook/{TOKEN}", methods=['POST'])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    return "Unsupported Media Type", 415

@app.route("/")
def index():
    return "Bot is running on Render!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
