import telebot
from telebot import types
import google.generativeai as genai
import os
from flask import Flask
import threading
import json

# --- SETUP ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = 1152974866  # <<< REPLACE THIS WITH YOUR TELEGRAM ID

USERS_FILE = 'users.json'
app = Flask(__name__)

# --- USER DATA FUNCTIONS ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, indent=4, ensure_ascii=False)

# --- WEB SERVER FOR RENDER ---
@app.route('/')
def index():
    return "Bot is running!"

def run_flask_app():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# --- BOT AND AI INITIALIZATION ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini model configured successfully.")
except Exception as e:
    print(f"!!! GEMINI CONFIG ERROR: {e}")
    model = None

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
users = load_users()
print("Bot starting with user approval system...")

# --- ADMIN DECORATOR ---
def is_admin(message):
    return message.from_user.id == ADMIN_ID

# --- USER REGISTRATION AND APPROVAL ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = str(message.from_user.id)
    user_data = users.get(user_id)

    if user_data:
        status = user_data.get('status', 'rejected')
        if status == 'allowed':
            bot.reply_to(message, "Welcome back! You are an approved user.")
        elif status == 'pending':
            bot.reply_to(message, "Your request for access is still pending.")
        else: # rejected
            bot.reply_to(message, "Sorry, your request for access was denied.")
    else:
        # New user
        first_name = message.from_user.first_name
        username = message.from_user.username or "not provided"
        
        users[user_id] = {'first_name': first_name, 'username': username, 'status': 'pending'}
        save_users(users)
        
        bot.reply_to(message, "Hello! Your request for access has been sent to the administrator. Please wait for approval.")
        
        # Send notification to admin (this is the corrected, safer version)
        markup = types.InlineKeyboardMarkup()
        btn_allow = types.InlineKeyboardButton("✅ Allow", callback_data=f"allow_{user_id}")
        btn_reject = types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
        markup.add(btn_allow, btn_reject)
        
        admin_text = (f"❗️ New access request:\n\n"
                      f"Name: {first_name}\n"
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
        
        bot.edit_message_text(f"Decision made: {new_status} for user {user_id}.", call.message.chat.id, call.message.message_id)
        
        if new_status == 'allowed':
            bot.send_message(user_id, "✅ Your request for access has been approved! You can now ask questions.")
        else:
            bot.send_message(user_id, "❌ Your request for access has been denied.")
    else:
        bot.edit_message_text("Error: User not found.", call.message.chat.id, call.message.message_id)

# --- MAIN MESSAGE HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = str(message.from_user.id)
    user_data = users.get(user_id)

    if not user_data or user_data.get('status') != 'allowed':
        bot.reply_to(message, "You do not have access. Please send /start to request access.")
        return
        
    if not model:
        bot.reply_to(message, "Sorry, the AI model is not configured correctly.")
        return
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"!!! AN ERROR OCCURRED: {e}")
        bot.reply_to(message, "Sorry, an error occurred while processing your request.")

# --- LAUNCH ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    print("Bot is running and polling for messages.")
    bot.polling(non_stop=True)

