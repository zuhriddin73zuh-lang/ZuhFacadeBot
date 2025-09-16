import os
import logging
from flask import Flask, request
import telebot

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv('TELEGRAM_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', '-1094323262'))  # ваш личный ID

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Вопросы на двух языках
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

# Благодарности
THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi. Tez orada siz bilan bog'lanamiz."
}

# Хранение состояния пользователей
user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        chat_id = message.chat.id
        text = message.text or ""
        
        # Определяем язык
        if 'uz' in text:
            lang = 'uz'
        else:
            lang = 'ru'
        
        # Инициализируем данные пользователя
        user_data[chat_id] = {
            'lang': lang,
            'step': 0,
            'answers': []
        }
        
        # Задаем первый вопрос
        bot.send_message(chat_id, QUESTIONS[lang][0])
        
    except Exception as e:
        logger.error(f"Error in handle_start: {e}")

@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    try:
        chat_id = message.chat.id
        
        # Проверяем, начал ли пользователь диалог
        if chat_id not in user_data:
            bot.send_message(chat_id, "Пожалуйста, начните с /start")
            return
        
        user = user_data[chat_id]
        lang = user['lang']
        step = user['step']
        
        # Обрабатываем ответ
        if step < 4:  # Первые 4 вопроса требуют текст
            if message.content_type != 'text':
                bot.send_message(chat_id, "Пожалуйста, ответьте текстом" if lang == 'ru' else "Iltimos, matn bilan javob bering")
                return
            
            user['answers'].append(message.text)
            user['step'] += 1
            
            # Задаем следующий вопрос
            if user['step'] < 5:
                bot.send_message(chat_id, QUESTIONS[lang][user['step']])
            else:
                # Все ответы получены
                send_application(user['answers'], lang, chat_id)
                bot.send_message(chat_id, THANK_YOU[lang])
                del user_data[chat_id]
                
        else:  # 5-й вопрос (комментарий или фото)
            if message.content_type == 'photo':
                user['answers'].append("Фото приложено" if lang == 'ru' else "Rasm qo'shildi")
            else:
                user['answers'].append(message.text)
            
            # Завершаем заявку
            send_application(user['answers'], lang, chat_id)
            bot.send_message(chat_id, THANK_YOU[lang])
            del user_data[chat_id]
            
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")

def send_application(answers, lang, chat_id):
    """Отправляем заявку в группу"""
    try:
        name, address, phone, square, comment = answers
        
        if lang == 'ru':
            text = f"📋 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратура: {square}\n💬 Комментарий: {comment}"
        else:
            text = f"📋 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Maydon: {square}\n💬 Izoh: {comment}"
        
        bot.send_message(GROUP_ID, text)
        
    except Exception as e:
        logger.error(f"Error sending application: {e}")

# Обработчик вебхука
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Invalid content type', 400

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

