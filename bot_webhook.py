# bot_webhook.py
# Запускать через gunicorn: gunicorn bot_webhook:app --bind 0.0.0.0:$PORT
import os
import re
from flask import Flask, request, abort
import telebot
from telebot import types

# --- Настройка через переменные окружения (на Render: Environment) ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")          # обязательно установить
GROUP_ID = os.environ.get("GROUP_ID")             # например: -1001234567890
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")       # например: https://your-service.onrender.com/webhook

if not TOKEN or not GROUP_ID:
    raise RuntimeError("TELEGRAM_TOKEN и GROUP_ID должны быть установлены в окружении")

GROUP_ID = int(GROUP_ID)

# --- Инициализация ---
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Простое хранилище состояний (в проде: лучше Redis или DB)
STATE = {}  # { chat_id: { 'lang': 'rus'|'uz', 'step': 'name'|'phone'|'comment', 'name':..., 'phone':... } }

# Тексты на двух языках
TEXTS = {
    "rus": {
        "choose": "Выберите язык / Tilni tanlang:",
        "ask_name": "Как Вас зовут?",
        "ask_phone": "Отправьте ваш телефон (или нажмите кнопку отправить контакт).",
        "phone_invalid": "Неправильный номер. Введите ещё раз (цифры, + и пробелы допустимы).",
        "ask_comment": "Комментарий / Адрес / Кратко опишите задачу (можно оставить пустым).",
        "thanks": "Спасибо, заявка принята. Мы свяжемся с вами.",
        "submission": "<b>Новая заявка</b>\nИмя: {name}\nТелефон: {phone}\nКомментарий: {comment}\nОт: @{username} ({chat_id})"
    },
    "uz": {
        "choose": "Tilni tanlang / Выберите язык:",
        "ask_name": "Ismingiz nima?",
        "ask_phone": "Telefon raqamingizni yuboring (yoki kontaktni yuborish tugmasini bosing).",
        "phone_invalid": "Noto'g'ri raqam. Iltimos qayta kiriting.",
        "ask_comment": "Izoh / Manzil / Vazifani qisqacha yozing (bo'sh qoldirish mumkin).",
        "thanks": "Rahmat, so'rov qabul qilindi. Siz bilan bog'lanamiz.",
        "submission": "<b>Yangi so'rov</b>\nIsm: {name}\nTelefon: {phone}\nIzoh: {comment}\nKimdan: @{username} ({chat_id})"
    }
}

# --- Хэндлеры бота ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    # Inline-кнопки выбора языка
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Русский", callback_data="lang_rus"),
           types.InlineKeyboardButton("O'zbek", callback_data="lang_uz"))
    bot.send_message(chat_id, TEXTS['rus']['choose'], reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("lang_"))
def callback_lang(call):
    chat_id = call.message.chat.id
    lang = 'rus' if call.data == 'lang_rus' else 'uz'
    STATE[chat_id] = {'lang': lang, 'step': 'name'}
    bot.answer_callback_query(call.id)
    bot.send_message(chat_id, TEXTS[lang]['ask_name'])

# Главный handler — получает текст и контакты
@bot.message_handler(content_types=['text', 'contact'])
def handle_all(message):
    chat_id = message.chat.id
    user_state = STATE.get(chat_id)

    if not user_state:
        # Просим нажать /start, если пользователь не выбрал язык
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(types.KeyboardButton("/start"))
        bot.send_message(chat_id, "Нажмите /start чтобы начать / Boshlash uchun /start bosing.", reply_markup=kb)
        return

    lang = user_state.get('lang', 'rus')
    step = user_state.get('step', 'name')

    # --- Шаг: имя ---
    if step == 'name':
        name = (message.text or "").strip()
        if not name:
            bot.send_message(chat_id, TEXTS[lang]['ask_name'])
            return
        user_state['name'] = name
        user_state['step'] = 'phone'
        # Предложим отправить контакт кнопкой
        kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        kb.add(types.KeyboardButton(TEXTS[lang]['ask_phone'], request_contact=True))
        bot.send_message(chat_id, TEXTS[lang]['ask_phone'], reply_markup=kb)
        return

    # --- Шаг: телефон ---
    if step == 'phone':
        phone = None
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = (message.text or "").strip()
        # Простая валидация: минимально 6 цифр
        phone_clean = re.sub(r'[^\d\+]', '', phone or "")
        if not phone_clean or len(re.sub(r'\D', '', phone_clean)) < 6:
            bot.send_message(chat_id, TEXTS[lang]['phone_invalid'])
            return
        user_state['phone'] = phone_clean
        user_state['step'] = 'comment'
        # убрать клавиатуру с кнопкой контакта
        kb = types.ReplyKeyboardRemove()
        bot.send_message(chat_id, TEXTS[lang]['ask_comment'], reply_markup=kb)
        return

    # --- Шаг: комментарий ---
    if step == 'comment':
        comment = (message.text or "").strip()
        user_state['comment'] = comment or "-"
        # Сформируем сообщение в группу
        name = user_state.get('name', '-')
        phone = user_state.get('phone', '-')
        username = message.from_user.username or ""
        submission = TEXTS[lang]['submission'].format(
            name=escape_html(name),
            phone=escape_html(phone),
            comment=escape_html(user_state['comment']),
            username=escape_html(username),
            chat_id=chat_id
        )
        try:
            bot.send_message(GROUP_ID, submission, parse_mode='HTML')
        except Exception as e:
            # если отправка в группу не удалась — уведомим пользователя (и залогируем)
            bot.send_message(chat_id, "Ошибка при отправке заявки в группу. Свяжитесь с админом.")
            print("Error sending to group:", e)
            # не удаляем состояние — можно попытаться снова
            return

        # Подтверждение пользователю
        bot.send_message(chat_id, TEXTS[lang]['thanks'])
        # Очистим состояние
        STATE.pop(chat_id, None)
        return

# --- Вебхук endpoint для Telegram ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') != 'application/json':
        abort(403)
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# Простая корневая страница — проверка
@app.route('/')
def index():
    return "OK", 200

# Утилита (простая экранизация HTML)
def escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# --- Установка webhook при старте (если задан WEBHOOK_URL) ---
def set_webhook_if_needed():
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            # Telegram требует полный URL до endpoint'а
            bot.set_webhook(url=WEBHOOK_URL)
            print("Webhook установлен ->", WEBHOOK_URL)
        except Exception as e:
            print("Не удалось установить webhook:", e)

# Выполнить при импорте (gunicorn импортирует модуль)
set_webhook_if_needed()


