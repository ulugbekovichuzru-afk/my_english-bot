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
LOG_CHANNEL_ID = os.environ.get('LOG_CHANNEL_ID') # ID вашего канала для логов
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
admin_states = {} # Для хранения состояний админа

print("Бот запускается с финальной версией админ-панели...")

# --- АДМИН-ПАНЕЛЬ И ЕЕ ЛОГИКА ---

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('📊 Статистика')
    btn2 = types.KeyboardButton('👥 Управление учениками')
    btn3 = types.KeyboardButton('📢 Рассылка')
    markup.add(btn1, btn2, btn3)
    return markup

@bot.message_handler(commands=['admin'], func=lambda m: m.from_user.id == ADMIN_ID)
def show_admin_panel(message):
    bot.reply_to(message, "⚙️ Админ-панель:", reply_markup=admin_keyboard())

# --- Обработчики кнопок админ-панели ---

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '📊 Статистика')
def handle_stats(message):
    stats = {'allowed': 0, 'pending': 0, 'rejected': 0}
    for data in users.values():
        stats[data.get('status', 'rejected')] += 1
    
    reply = (f"📊 Статистика пользователей:\n\n"
             f"✅ Одобренные ученики: {stats['allowed']}\n"
             f"⏳ Ожидают одобрения: {stats['pending']}\n"
             f"❌ Отклоненные: {stats['rejected']}\n"
             f"Всего в базе: {len(users)}")
    bot.reply_to(message, reply)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '👥 Управление учениками')
def handle_manage_students(message):
    reply = ("Для управления учеником, отправьте мне его Telegram ID.\n\n"
             "Чтобы получить список всех учеников и их ID, отправьте команду /list.")
    bot.reply_to(message, reply)

@bot.message_handler(commands=['list'], func=lambda m: m.from_user.id == ADMIN_ID)
def handle_list_command(message):
    allowed_users = {uid: data for uid, data in users.items() if data.get('status') == 'allowed'}
    if not allowed_users:
        bot.reply_to(message, "Пока нет ни одного одобренного ученика.")
        return
    
    reply = "👥 Список одобренных учеников:\n\n"
    for user_id, data in allowed_users.items():
        reply += (f"Имя: {data.get('first_name', 'N/A')}\n"
                  f"ID: `{user_id}`\n\n")
    bot.reply_to(message, reply, parse_mode='Markdown')

@bot.message_handler(commands=['delete'], func=lambda m: m.from_user.id == ADMIN_ID)
def handle_delete_command(message):
    try:
        user_id_to_delete = message.text.split()[1]
        if user_id_to_delete in users:
            del users[user_id_to_delete]
            save_users(users)
            bot.reply_to(message, f"✅ Пользователь {user_id_to_delete} полностью удален из базы.")
        else:
            bot.reply_to(message, "❌ Пользователь с таким ID не найден.")
    except IndexError:
        bot.reply_to(message, "Использование: /delete <user_id>")
        
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == '📢 Рассылка')
def handle_broadcast(message):
    msg = bot.reply_to(message, "Напишите сообщение, которое хотите разослать всем одобренным ученикам.")
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    text_to_send = message.text
    sent_count = 0
    allowed_users_ids = [uid for uid, data in users.items() if data.get('status') == 'allowed']
    
    if not allowed_users_ids:
        bot.reply_to(message, "Нет одобренных учеников для рассылки.")
        return

    for user_id in allowed_users_ids:
        try:
            bot.send_message(user_id, text_to_send)
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    
    bot.reply_to(message, f"📢 Рассылка завершена. Сообщение отправлено {sent_count} из {len(allowed_users_ids)} учеников.")

# --- ЛОГИКА РЕГИСТРАЦИИ И ОДОБРЕНИЯ ---
# (Код остается без изменений)
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id == ADMIN_ID:
        show_admin_panel(message)
        return
    user_id = str(message.from_user.id)
    # ... (остальной код handle_start без изменений)
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

@bot.callback_query_handler(func=lambda call: call.from_user.id == ADMIN_ID)
def handle_approval(call):
    # (Код остается без изменений)
    action, user_id = call.data.split('_')
    if user_id in users:
        new_status = 'allowed' if action == 'allow' else 'rejected'
        users[user_id]['status'] = new_status
        save_users(users)
        bot.edit_message_text(f"Решение принято: {new_status} для {user_id}.", call.message.chat.id, call.message.message_id)
        if new_status == 'allowed': bot.send_message(user_id, "✅ Ваша заявка одобрена!")
        else: bot.send_message(user_id, "❌ Ваша заявка отклонена.")

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ И ЛОГИРОВАНИЕ ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, используйте кнопки или команды.", reply_markup=admin_keyboard())
        return
    user_id = str(message.from_user.id)
    if not users.get(user_id) or users[user_id].get('status') != 'allowed':
        bot.reply_to(message, "У вас нет доступа. Отправьте /start для заявки.")
        return
    
    # Логирование в канал
    if LOG_CHANNEL_ID:
        try:
            log_text = f"Сообщение от {users[user_id].get('first_name', 'N/A')} (ID: {user_id}):\n\n{message.text}"
            bot.send_message(LOG_CHANNEL_ID, log_text)
        except Exception as e:
            print(f"Не удалось отправить лог в канал: {e}")

    # Ответ от ИИ
    if not model:
        bot.reply_to(message, "Извините, модель ИИ не настроена.")
        return
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"!!! ОШИБКА GEMINI: {e}")
        bot.reply_to(message, "Извините, произошла ошибка.")

# --- ЗАПУСК ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    print("Бот запущен и готов к работе.")
    bot.polling(non_stop=True)
