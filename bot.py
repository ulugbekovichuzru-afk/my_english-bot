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
LOG_CHANNEL_ID = os.environ.get('LOG_CHANNEL_ID')
ADMIN_ID = 1152974866  # <<< ЗАМЕНИТЕ ЭТО НА ВАШ TELEGRAM ID

USERS_FILE = 'users.json'
app = Flask(__name__)

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ---
def load_users():
    if not os.path.exists(USERS_FILE): return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return {}

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
print("Бот запускается с финальной кнопочной админ-панелью...")

# --- АДМИН-ПАНЕЛЬ И ЕЕ ЛОГИКА ---
def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton('📊 Статистика'), types.KeyboardButton('👥 Управление учениками'), types.KeyboardButton('📢 Рассылка'))
    return markup

@bot.message_handler(commands=['admin'], func=lambda m: m.from_user.id == ADMIN_ID)
def show_admin_panel(message):
    bot.reply_to(message, "⚙️ Админ-панель:", reply_markup=admin_keyboard())

# --- Обработчики кнопок админ-панели ---
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '📊 Статистика')
def handle_stats(message):
    stats = {'allowed': 0, 'pending': 0, 'rejected': 0}
    for data in users.values(): stats[data.get('status', 'rejected')] += 1
    reply = f"📊 Статистика:\n\n✅ Одобрено: {stats['allowed']}\n⏳ Ожидают: {stats['pending']}\n❌ Отклонено/Забанено: {stats['rejected']}\n\nВсего в базе: {len(users)}"
    bot.reply_to(message, reply)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '👥 Управление учениками')
def handle_manage_students_button(message):
    allowed_users = {uid: data for uid, data in users.items() if data.get('status') == 'allowed'}
    if not allowed_users:
        bot.reply_to(message, "Нет одобренных учеников для управления.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for uid, data in allowed_users.items():
        markup.add(types.InlineKeyboardButton(f"{data.get('first_name', 'N/A')} ({uid})", callback_data=f"manage_{uid}"))
    bot.reply_to(message, "Выберите ученика для управления:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '📢 Рассылка')
def handle_broadcast_button(message):
    msg = bot.reply_to(message, "Напишите сообщение для рассылки всем одобренным ученикам.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    text_to_send = message.text
    sent_count = 0
    allowed_ids = [uid for uid, data in users.items() if data.get('status') == 'allowed']
    if not allowed_ids:
        bot.reply_to(message, "Нет учеников для рассылки.")
        return
    for user_id in allowed_ids:
        try:
            bot.send_message(user_id, text_to_send)
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить сообщение {user_id}: {e}")
    bot.reply_to(message, f"📢 Рассылка завершена. Отправлено {sent_count} из {len(allowed_ids)} ученикам.")

# --- ЛОГИКА РЕГИСТРАЦИИ ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id == ADMIN_ID: show_admin_panel(message); return
    user_id = str(message.from_user.id)
    if user_id in users and users[user_id]['status'] == 'allowed':
        bot.reply_to(message, "Здравствуйте! Вы уже одобрены.")
    elif user_id in users and users[user_id]['status'] == 'pending':
        bot.reply_to(message, "Ваша заявка на рассмотрении.")
    else:
        first_name, username = message.from_user.first_name, message.from_user.username or "не указан"
        users[user_id] = {'first_name': first_name, 'username': username, 'status': 'pending'}
        save_users(users)
        bot.reply_to(message, "Здравствуйте! Ваша заявка отправлена администратору.")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Разрешить", callback_data=f"allow_{user_id}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}"))
        admin_text = f"❗️ Новый запрос на доступ:\n\nИмя: {first_name}\nUsername: @{username}\nID: {user_id}"
        bot.send_message(ADMIN_ID, admin_text, reply_markup=markup)

# --- ОБРАБОТЧИК ВСЕХ НАЖАТИЙ НА ИНЛАЙН-КНОПКИ ---
@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
def handle_callbacks(call):
    action, user_id = call.data.split('_', 1)

    if action == 'allow' or action == 'reject':
        if user_id in users:
            new_status = 'allowed' if action == 'allow' else 'rejected'
            users[user_id]['status'] = new_status
            save_users(users)
            bot.edit_message_text(f"Решение принято: {new_status} для {user_id}.", call.message.chat.id, call.message.message_id)
            if new_status == 'allowed': bot.send_message(user_id, "✅ Ваша заявка одобрена!")
            else: bot.send_message(user_id, "❌ Ваша заявка отклонена.")
    
    elif action == 'manage':
        if user_id in users:
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("❌ Забанить", callback_data=f"reject_{user_id}"),
                       types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{user_id}"))
            user_info = users[user_id]
            bot.edit_message_text(f"Управление учеником:\nИмя: {user_info.get('first_name', 'N/A')}\nID: `{user_id}`",
                                  call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif action == 'delete':
        if user_id in users:
            name = users[user_id].get('first_name', user_id)
            del users[user_id]
            save_users(users)
            bot.edit_message_text(f"✅ Ученик {name} ({user_id}) полностью удален из базы.", call.message.chat.id, call.message.message_id)

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ И ЛОГИРОВАНИЕ ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, используйте кнопки или команду /admin.", reply_markup=admin_keyboard()); return
    user_id = str(message.from_user.id)
    if not users.get(user_id) or users[user_id].get('status') != 'allowed':
        bot.reply_to(message, "У вас нет доступа. Отправьте /start для заявки."); return
    
    if LOG_CHANNEL_ID:
        try: bot.send_message(LOG_CHANNEL_ID, f"Сообщение от {users[user_id].get('first_name', 'N/A')} ({user_id}):\n\n{message.text}")
        except Exception as e: print(f"Не удалось отправить лог: {e}")

    if not model: bot.reply_to(message, "Извините, модель ИИ не настроена."); return
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"!!! ОШИБКА GEMINI: {e}"); bot.reply_to(message, "Извините, произошла ошибка.")

# --- ЗАПУСК ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    print("Бот запущен и готов к работе.")
    bot.polling(non_stop=True)
