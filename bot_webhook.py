import os
import logging
from flask import Flask, request
import telebot

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "7592969962:AAE93nt3NRENC9LCxfomvONl7zqozS2SZh8"
GROUP_ID = -1094323262  # Временный ID, заменим потом

logger.info("✅ Bot starting...")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 🔥 КОМАНДА ДЛЯ ПОЛУЧЕНИЯ ID
@bot.message_handler(commands=['getid'])
def get_chat_id(message):
    chat_id = message.chat.id
    bot.send_message(message.chat.id, f"🆔 ID этого чата: `{chat_id}`", parse_mode='Markdown')
    logger.info(f"Chat ID: {chat_id}")

# Остальной код остается без изменений...
QUESTIONS = {
    "ru": ["Ваше имя?", "Адрес?", "Телефон?", "Площадь?", "Комментарий?"],
    "uz": ["Ismingiz?", "Manzil?", "Telefon?", "Maydon?", "Izoh?"]
}

user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    lang = 'uz' if 'uz' in message.text else 'ru'
    user_data[chat_id] = {'lang': lang, 'step': 0, 'answers': []}
    bot.send_message(chat_id, QUESTIONS[lang][0])

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        return
        
    user = user_data[chat_id]
    user['answers'].append(message.text)
    user['step'] += 1
    
    if user['step'] < len(QUESTIONS[user['lang']]):
        bot.send_message(chat_id, QUESTIONS[user['lang']][user['step']])
    else:
        # Временно отправляем заявку в личные сообщения
        bot.send_message(chat_id, "✅ Заявка принята! ID группы пока настраивается.")
        del user_data[chat_id]

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return 'OK'

@app.route('/')
def home():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


