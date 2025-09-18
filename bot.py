import telebot
from telebot import types
import google.generativeai as genai
import os
from flask import Flask
import threading
import json

# --- НАСТРОЙКА ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = 1152974866  # <<< ЗАМЕНИТЕ ЭТО НА ВАШ TELEGRAM ID

USERS_FILE = 'users.json'
app = Flask(__name__)

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, indent=4, ensure_ascii=False)

# --- ВЕБ-СЕРВЕР (для Render) ---
@app.route('/')
def index(): return "Bot is running!"

def run_flask_app():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# --- ИНИЦИАЛИЗАЦИЯ БОТА И ИИ ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Модель Gemini успешно настроена.")
except Exception as e:
    print(f"!!! ОШИБКА НАСТРОЙКИ GEMINI: {e}")
    model = None

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
users = load_users()
admin_states = {} # Для хранения состояний админа в многошаговых командах

print("Бот запускается с админ-панелью...")

# --- АДМИН-ПАНЕЛЬ И ЕЕ ЛОГИКА ---

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('📊 Статистика')
    btn2 = types.KeyboardButton('👥 Список учеников')
    markup.add(btn1, btn2)
    return markup

@bot.message_handler(commands=['admin'], func=lambda m: m.from_user.id == ADMIN_ID)
def show_admin_panel(message):
    bot.reply_to(message, "⚙️ Админ-панель:", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '📊 Статистика')
def handle_stats(message):
    stats = {'allowed': 0, 'pending': 0, 'rejected': 0}
    for user_id, data in users.items():
        status = data.get('status', 'rejected')
        if status in stats:
            stats[status] += 1
    
    reply = (f"📊 Статистика пользователей:\n\n"
             f"✅ Одобренные ученики: {stats['allowed']}\n"
             f"⏳ Ожидают одобрения: {stats['pending']}\n"
             f"❌ Отклоненные/Забаненные: {stats['rejected']}\n\n"
             f"Всего в базе: {len(users)}")
    bot.reply_to(message, reply)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '👥 Список учеников')
def handle_list_students(message):
    allowed_users = {uid: data for uid, data in users.items() if data.get('status') == 'allowed'}
    if not allowed_users:
        bot.reply_to(message, "Пока нет ни одного одобренного ученика.")
        return
    
    reply = "👥 Список одобренных учеников:\n\n"
    for user_id, data in allowed_users.items():
        reply += (f"Имя: {data.get('first_name', 'N/A')}\n"
                  f"ID: `{user_id}`\n\n") # Используем Markdown для удобного копирования ID
    bot.reply_to(message, reply, parse_mode='Markdown')

# --- ЛОГИКА РЕГИСТРАЦИИ И ОДОБРЕНИЯ ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id == ADMIN_ID:
        show_admin_panel(message)
        return

    user_id = str(message.from_user.id)
    user_data = users.get(user_id)

    if user_data:
        status = user_data.get('status', 'rejected')
        if status == 'allowed':
            bot.reply_to(message, "Здравствуйте! Вы уже одобрены. Можете задавать вопросы.")
        elif status == 'pending':
            bot.reply_to(message, "Ваша заявка на доступ еще на рассмотрении. Пожалуйста, ожидайте.")
        else: # rejected
            bot.reply_to(message, "К сожалению, ваша заявка на доступ была отклонена.")
    else:
        # Новый пользователь
        first_name = message.from_user.first_name
        username = message.from_user.username or "не указан"
        
        users[user_id] = {'first_name': first_name, 'username': username, 'status': 'pending'}
        save_users(users)
        
        bot.reply_to(message, "Здравствуйте! Ваша заявка на доступ отправлена администратору. Пожалуйста, ожидайте решения.")
        
        markup = types.InlineKeyboardMarkup()
        btn_allow = types.InlineKeyboardButton("✅ Разрешить", callback_data=f"allow_{user_id}")
        btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
        markup.add(btn_allow, btn_reject)
        
        admin_text = (f"❗️ Новый запрос на доступ:\n\n"
                      f"Имя: {first_name}\n"
                      f"Username: @{username}\n"
                      f"Telegram ID: {user_id}")
        bot.send_message(ADMIN_ID, admin_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
def handle_approval(call):
    action, user_id = call.data.split('_')
    
    if user_id in users:
        new_status = 'allowed' if action == 'allow' else 'rejected'
        users[user_id]['status'] = new_status
        save_users(users)
        
        bot.edit_message_text(f"Решение принято: {new_status} для пользователя {user_id}.", call.message.chat.id, call.message.message_id)
        
        if new_status == 'allowed':
            bot.send_message(user_id, "✅ Ваша заявка на доступ одобрена! Теперь вы можете задавать вопросы.")
        else:
            bot.send_message(user_id, "❌ Ваша заявка на доступ была отклонена.")
    else:
        bot.edit_message_text("Ошибка: пользователь не найден.", call.message.chat.id, call.message.message_id)


# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    # Админ использует только кнопки и команды
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, используйте кнопки админ-панели или отправьте /admin.", reply_markup=admin_keyboard())
        return

    user_id = str(message.from_user.id)
    user_data = users.get(user_id)

    if not user_data or user_data.get('status') != 'allowed':
        bot.reply_to(message, "У вас нет доступа. Пожалуйста, отправьте /start, чтобы подать заявку.")
        return
        
    if not model:
        bot.reply_to(message, "Извините, модель ИИ не настроена.")
        return
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"!!! ПРОИЗОШЛА ОШИБКА: {e}")
        bot.reply_to(message, "Извините, произошла ошибка при обработке вашего запроса.")


# --- ЗАПУСК ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    print("Бот запущен и готов к работе.")
    bot.polling(non_stop=True)
