import telebot
import google.generativeai as genai
import os
from flask import Flask
import threading

# --- SETUP ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
app = Flask(__name__) # This is for the web server part

# --- Dummy Web Server to Keep Render Happy ---
@app.route('/')
def index():
    return "Bot is running!"

def run_flask_app():
    # Render provides the port to use in the PORT environment variable
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# --- BOT INITIALIZATION ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini model configured successfully.")
except Exception as e:
    print(f"!!! ERROR CONFIGURING GEMINI: {e}")
    model = None

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
print("Bot starting...")

# --- BOT LOGIC ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not model:
        bot.reply_to(message, "Sorry, the AI model is not configured correctly.")
        return
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"!!! AN ERROR OCCURRED: {e}")
        bot.reply_to(message, "Sorry, an error occurred while processing your request.")

# --- LAUNCH EVERYTHING ---
if __name__ == "__main__":
    # Start the web server in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    
    # Start the bot's polling
    print("Bot is running and polling for messages.")
    bot.polling(non_stop=True)

