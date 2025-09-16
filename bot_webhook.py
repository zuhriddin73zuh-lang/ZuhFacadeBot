
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        logger.info(f"📨 Received: {message.text}")
        chat_id = message.chat.id
        
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

# 🔥 ВАЖНО: Добавляем обработчик для ВСЕХ сообщений
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        chat_id = message.chat.id
        
        # Проверяем, начал ли пользователь диалог
        if chat_id not in user_data:
            bot.send_message(chat_id, "Пожалуйста, начните с /start")
            return
        
        user = user_data[chat_id]
        lang = user['lang']
        step = user['step']
        answers = user['answers']
        
        logger.info(f"💬 Processing step {step} for chat {chat_id}")
        
        # Сохраняем ответ
        answers.append(message.text)
        user['step'] += 1
        
        # Задаем следующий вопрос или завершаем
        if user['step'] < len(QUESTIONS[lang]):
            bot.send_message(chat_id, QUESTIONS[lang][user['step']])
        else:
            # Все ответы получены
            send_application(answers, lang, chat_id)
            bot.send_message(chat_id, THANK_YOU[lang])
            del user_data[chat_id]
            
    except Exception as e:
        logger.error(f"❌ Error in handle_all_messages: {e}")

def send_application(answers, lang, chat_id):
    try:
        name, address, phone, square, comment = answers
        
        if lang == 'ru':
            text = f"📋 Новая заявка\n\n👤 Имя: {name}\n🏠 Адрес: {address}\n📞 Телефон: {phone}\n📐 Квадратура: {square}\n💬 Комментарий: {comment}"
        else:
            text = f"📋 Yangi ariza\n\n👤 Ism: {name}\n🏠 Manzil: {address}\n📞 Telefon: {phone}\n📐 Maydon: {square}\n💬 Izoh: {comment}"
        
        bot.send_message(GROUP_ID, text)
        logger.info(f"📤 Application sent to group {GROUP_ID}")
        
    except Exception as e:
        logger.error(f"❌ Error sending application: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_data = request.get_json()
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return 'OK'
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return 'Error', 500

@app.route('/')
def home():
    return '✅ Bot is running!'

if __name__ == '__main__':
    logger.info("🚀 Starting Flask server...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

