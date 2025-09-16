# Временно добавить для проверки
import os
print("ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:", os.getenv('TELEGRAM_TOKEN')) import logging
import telebot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv('TELEGRAM_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', '-1094323262'))

logger.info("✅ Bot starting...")
logger.info(f"Token: {TOKEN}")
logger.info(f"Group ID: {GROUP_ID}")

bot = telebot.TeleBot(TOKEN)

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

THANK_YOU = {
    "ru": "✅ Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время.",
    "uz": "✅ Rahmat! So'rovingiz qabul qilindi. Tez orada siz bilan bog'lanamiz."
}

user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        logger.info(f"📨 Received: {message.text}")
        chat_id = message.chat.id
        
        # Определяем язык
        if 'uz' in message.text:
            lang = 'uz'
        else:
            lang = 'ru'
            
        logger.info(f"🌐 Language: {lang} for chat {chat_id}")
        
        user_data[chat_id] = {'lang': lang, 'step': 0, 'answers': []}
        bot.send_message(chat_id, QUESTIONS[lang][0])
        logger.info(f"✅ First question sent to {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")

@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    try:
        chat_id = message.chat.id
        
        if chat_id not in user_data:
            bot.send_message(chat_id, "Пожалуйста, начните с /start")
            return
        
        user = user_data[chat_id]
        lang = user['lang']
        step = user['step']
        
        if step < 4:
            if message.content_type != 'text':
                bot.send_message(chat_id, "Пожалуйста, ответьте текстом" if lang == 'ru' else "Iltimos, matn bilan javob bering")
                return
            
            user['answers'].append(message.text)
            user['step'] += 1
            
            if user['step'] < 5:
                bot.send_message(chat_id, QUESTIONS[lang][user['step']])
            else:
                # Завершаем заявку
                send_application(user['answers'], lang, chat_id)
                bot.send_message(chat_id, THANK_YOU[lang])
                del user_data[chat_id]
                
        else:
            if message.content_type == 'photo':
                user['answers'].append("Фото приложено" if lang == 'ru' else "Rasm qo'shildi")
            else:
                user['answers'].append(message.text)
            
            send_application(user['answers'], lang, chat_id)
            bot.send_message(chat_id, THANK_YOU[lang])
            del user_data[chat_id]
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")

def send_application(answers, lang, chat_id):
    try:
        name, address, phone, square, comment = answers
        
        if lang == 'ru':
            text = f"📋 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратура: {square}\n💬 Комментарий: {comment}"
        else:
            text = f"📋 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Maydon: {square}\n💬 Izoh: {comment}"
        
        bot.send_message(GROUP_ID, text)
        
    except Exception as e:
        logger.error(f"❌ Error sending application: {e}")

logger.info("🚀 Starting bot in polling mode...")
bot.polling(none_stop=True)

