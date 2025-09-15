import os
import telebot
from flask import Flask, request

TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "-1094323262"))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Простые вопросы
QUESTIONS = {
    "ru": ["Ваше имя?", "Адрес?", "Телефон?", "Площадь?", "Комментарий?"],
    "uz": ["Ismingiz?", "Manzil?", "Telefon?", "Maydon?", "Izoh?"]
}

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Выбери язык / Til tanlang")
    bot.send_message(chat_id, "Русский / Uzbek")
    bot.register_next_step_handler(message, choose_language)

def choose_language(message):
    chat_id = message.chat.id
    text = message.text.lower()
    
    if text in ['русский', 'russian', 'ru']:
        lang = "ru"
    else:
        lang = "uz"
        
    bot.send_message(chat_id, QUESTIONS[lang][0])
    bot.register_next_step_handler(message, process_name, lang, 0, [])

def process_name(message, lang, step, answers):
    chat_id = message.chat.id
    answers.append(message.text)
    step += 1
    
    if step < len(QUESTIONS[lang]):
        bot.send_message(chat_id, QUESTIONS[lang][step])
        bot.register_next_step_handler(message, process_name, lang, step, answers)
    else:
        # Отправляем заявку
        application = f"Новая заявка:\nИмя: {answers[0]}\nАдрес: {answers[1]}\nТелефон: {answers[2]}\nПлощадь: {answers[3]}\nКомментарий: {answers[4]}"
        bot.send_message(GROUP_ID, application)
        bot.send_message(chat_id, "✅ Заявка отправлена!" if lang == "ru" else "✅ So'rov yuborildi!")

@app.route("/webhook", methods=["POST"])
def webhook():
    json_data = request.get_json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK"

@app.route("/")
def home():
    return "Бот работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
