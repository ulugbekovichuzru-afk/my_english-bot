import telebot
import google.generativeai as genai
import os # Нужен для чтения переменных окружения

# --- НАСТРОЙКА ---
# Ключи будут считываться с сервера, где развернут бот
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- ИНИЦИАЛИЗАЦИЯ МОДЕЛИ И БОТА ---
# Настраиваем модель Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Модель Gemini успешно настроена.")
except Exception as e:
    print(f"Ошибка при настройке Gemini: {e}")
    model = None

# Создаем экземпляр бота
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

print("Бот запускается...")

# --- ЛОГИКА БОТА ---
# Обработчик для всех входящих текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_question = message.text
    print(f"Получен вопрос от пользователя {chat_id}: {user_question}")

    # Проверка, что модель была успешно загружена
    if not model:
        bot.send_message(chat_id, "😕 Извините, модель ИИ сейчас не настроена. Пожалуйста, проверьте логи сервера.")
        return

    try:
        # Сообщаем пользователю, что мы думаем над его вопросом
        thinking_message = bot.send_message(chat_id, "🤔 Думаю...")
        
        # Отправляем запрос в Gemini
        response = model.generate_content(user_question)
        
        # Заменяем сообщение "Думаю..." на готовый ответ
        bot.edit_message_text(chat_text=response.text, chat_id=chat_id, message_id=thinking_message.message_id)
        print(f"Ответ для {chat_id} отправлен.")
        
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        bot.send_message(chat_id, "😕 Ой, что-то пошло не так. Попробуйте, пожалуйста, немного позже.")

# --- ЗАПУСК ---
print("Бот запущен и готов к работе.")
# Команда, которая заставляет бота постоянно проверять наличие новых сообщений
bot.polling(non_stop=True)