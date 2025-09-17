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
        return json.load(f)

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
print("Бот запускается с расширенной системой управления группами...")

# --- Декоратор для проверки админа ---
def is_admin(message):
    return message.from_user.id == ADMIN_ID

# --- НОВЫЕ АДМИНСКИЕ КОМАНДЫ ДЛЯ ГРУПП ---

@bot.message_handler(commands=['assign', 'move'], func=is_admin)
def assign_or_move_group(message):
    """Эта функция теперь обрабатывает и назначение, и перемещение."""
    try:
        parts = message.text.split(maxsplit=2)
        user_id = parts[1]
        group_name = parts[2]
        if user_id in users and users[user_id]['status'] == 'allowed':
            old_group = users[user_id].get('group', 'Без группы')
            users[user_id]['group'] = group_name
            save_users(users)
            bot.reply_to(message, f"✅ Успешно! Ученик {users[user_id]['first_name']} (`{user_id}`) перемещен из группы '{old_group}' в группу '{group_name}'.")
        else:
            bot.reply_to(message, "❌ Ошибка: Ученик с таким ID не найден или не одобрен.")
    except IndexError:
        bot.reply_to(message, "Использование: /assign <user_id> <group_name> ИЛИ /move <user_id> <group_name>")

@bot.message_handler(commands=['removefromgroup'], func=is_admin)
def remove_from_group(message):
    try:
        user_id = message.text.split()[1]
        if user_id in users and users[user_id]['status'] == 'allowed':
            users[user_id]['group'] = None # Убираем ученика из группы
            save_users(users)
            bot.reply_to(message, f"✅ Ученик {users[user_id]['first_name']} (`{user_id}`) удален из своей группы.")
        else:
            bot.reply_to(message, "❌ Ошибка: Ученик с таким ID не найден или не одобрен.")
    except IndexError:
        bot.reply_to(message, "Использование: /removefromgroup <user_id>")

@bot.message_handler(commands=['broadcast'], func=is_admin)
def broadcast_message(message):
    try:
        parts = message.text.split(maxsplit=2)
        group_name = parts[1]
        text_to_send = parts[2]
        
        sent_count = 0
        user_list = [uid for uid, data in users.items() if data.get('group') == group_name and data.get('status') == 'allowed']
        
        if not user_list:
            bot.reply_to(message, f"В группе '{group_name}' нет учеников для рассылки.")
            return

        for user_id in user_list:
            try:
                bot.send_message(user_id, text_to_send)
                sent_count += 1
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        
        bot.reply_to(message, f"📢 Рассылка для группы '{group_name}' завершена. Сообщение отправлено {sent_count} из {len(user_list)} учеников.")
    except IndexError:
        bot.reply_to(message, "Использование: /broadcast <group_name> <ваше сообщение>")

@bot.message_handler(commands=['listgroups'], func=is_admin)
def list_groups(message):
    groups = {}
    for user_id, data in users.items():
        if data.get('status') != 'allowed': continue # Показываем только одобренных учеников

        group = data.get('group', 'Нераспределенные') # Ученики без группы попадают сюда
        if group not in groups:
            groups[group] = []
        groups[group].append(f"{data.get('first_name', 'N/A')} (`{user_id}`)")
    
    if not groups:
        bot.reply_to(message, "Пока нет одобренных учеников.")
        return
        
    reply = "👥 Список групп и учеников:\n\n"
    for group_name, members in sorted(groups.items()):
        reply += f"*{group_name}*:\n"
        for member in members:
            reply += f"  - {member}\n"
        reply += "\n"
    bot.reply_to(message, reply, parse_mode='Markdown')


# --- ЛОГИКА РЕГИСТРАЦИИ И ОДОБРЕНИЯ (остается без изменений) ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = str(message.from_user.id)
    if user_id in users and users[user_id]['status'] == 'allowed':
        group_info = f"Вы в группе: *{users[user_id].get('group', 'Без группы')}*"
        bot.reply_to(message, f"Здравствуйте! Вы уже одобрены и можете пользоваться ботом.\n{group_info}", parse_mode='Markdown')
    elif user_id in users and users[user_id]['status'] == 'pending':
        bot.reply_to(message, "⏳ Ваша заявка на доступ все еще на рассмотрении.")
    else:
        first_name = message.from_user.first_name
        username = message.from_user.username or "не указан"
        users[user_id] = {'first_name': first_name, 'username': username, 'status': 'pending', 'group': None}
        save_users(users)
        bot.reply_to(message, "Здравствуйте! Ваша заявка на доступ отправлена администратору. Ожидайте решения.")
        
        markup = types.InlineKeyboardMarkup()
        btn_allow = types.InlineKeyboardButton("✅ Разрешить", callback_data=f"allow_{user_id}")
        btn_reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
        markup.add(btn_allow, btn_reject)
        admin_text = f"❗️ Новый запрос на доступ:\nИмя: {first_name}\nUsername: @{username}\nID: `{user_id}`"
        bot.send_message(ADMIN_ID, admin_text, reply_markup=markup, parse_mode='Markdown')

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

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ (остается без изменений) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.from_user.id)
    if user_id not in users or users[user_id].get('status') != 'allowed':
        bot.reply_to(message, "У вас нет доступа. Пожалуйста, отправьте команду /start, чтобы подать заявку.")
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
