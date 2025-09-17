import telebot
import google.generativeai as genai
import os

# --- SETUP ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- INITIALIZE MODEL AND BOT ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini model configured successfully.")
except Exception as e:
    print("!!! ERROR CONFIGURING GEMINI MODEL !!!")
    print(f"DETAILS: {e}")
    model = None

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

print("Bot is starting...")

# --- BOT LOGIC ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_question = message.text
    print(f"Received question from user {chat_id}: {user_question}")

    if not model:
        bot.send_message(chat_id, "😕 Sorry, the AI model was not loaded due to a setup error.")
        return

    try:
        thinking_message = bot.send_message(chat_id, "🤔 Thinking (debug mode)...")
        response = model.generate_content(user_question)
        bot.edit_message_text(chat_text=response.text, chat_id=chat_id, message_id=thinking_message.message_id)
        print(f"Reply sent to {chat_id}.")
        
    except Exception as e:
        # THIS IS THE MOST IMPORTANT PART
        # We print the detailed error to the Render logs
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! AN ERROR OCCURRED WHILE CALLING THE GEMINI API !!!")
        print(f"!!! ERROR DETAILS: {e}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # And we send a message to the user
        bot.send_message(chat_id, "😕 An error occurred while contacting the AI. The administrator can see the details.")

# --- LAUNCH ---
print("Bot is running and ready (debug mode).")
bot.polling(non_stop=True)
