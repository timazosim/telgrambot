import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from googlesearch import search
import logging

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv ("7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"
DATA_FILE = "bot_data.json"

# Initialize transformer model (distilgpt2 for lightweight performance)
generator = pipeline("text-generation", model="distilgpt2")

# Rate limiting configuration
RATE_LIMIT = 10  # Max messages per minute per user
user_timestamps = {}

# Load conversation data
def load_data():
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"users": {}}
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return {"users": {}}

# Save conversation data
def save_data(data):
    try:
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

# Check rate limit
def check_rate_limit(user_id):
    now = time.time()
    if user_id not in user_timestamps:
        user_timestamps[user_id] = []
    user_timestamps[user_id] = [t for t in user_timestamps[user_id] if now - t < 60]
    if len(user_timestamps[user_id]) >= RATE_LIMIT:
        return False
    user_timestamps[user_id].append(now)
    return True

# Search online with fallback
def search_online(query):
    try:
        results = list(search(query, num_results=3, lang="ru"))
        if results:
            return f"Вот что я нашёл: {results[0]}"
        return None
    except Exception as e:
        logger.error(f"Search error: {e}")
        return None

# Generate response using transformer model
def generate_response(prompt, context=""):
    try:
        input_text = f"{context}\nUser: {prompt}\nBot: "
        response = generator(input_text, max_length=150, num_return_sequences=1, truncation=True)[0]['generated_text']
        # Extract only the bot's response
        bot_response = response.split("Bot: ")[-1].strip()
        return bot_response
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return "Извини, что-то пошло не так. Попробуй ещё раз!"

# Command: /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}! Я твой умный бот, готовый ответить на любые вопросы. "
        "Задавай вопрос, и я найду ответ или придумаю что-то умное! 😄\n"
        "Команды: /start, /history, /clear"
    )

# Command: /history
def history(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data["users"] or not data["users"][user_id]:
        update.message.reply_text("История пуста! Задай мне вопрос, чтобы начать.")
        return
    
    response = "*Твоя история вопросов:*\n"
    for entry in data["users"][user_id][-5:]:  # Show last 5 entries
        timestamp = entry.get("timestamp", "Неизвестно")
        question = entry["question"]
        answer = entry["answer"]
        response += f"_{timestamp}_\n*Вопрос:* {question}\n*Ответ:* {answer}\n\n"
    
    update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

# Command: /clear
def clear(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id in data["users"]:
        data["users"][user_id] = []
        save_data(data)
        update.message.reply_text("История очищена!")
    else:
        update.message.reply_text("У тебя пока нет истории для очистки.")

# Handle text messages
def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_message = update.message.text.strip()
    
    # Rate limit check
    if not check_rate_limit(user_id):
        update.message.reply_text("Слишком много сообщений! Подожди минутку.")
        return
    
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = []
    
    # Load recent conversation context (last 3 messages)
    context = ""
    for entry in data["users"][user_id][-3:]:
        context += f"User: {entry['question']}\nBot: {entry['answer']}\n"
    
    # Try to find answer in history
    for entry in data["users"][user_id]:
        if entry["question"].lower() == user_message.lower():
            update.message.reply_text(f"Я уже отвечал: {entry['answer']}")
            return
    
    # Try online search
    answer = search_online(user_message)
    
    # Fallback to transformer model if search fails
    if not answer:
        answer = generate_response(user_message, context)
    
    # Save to history
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["users"][user_id].append({
        "question": user_message,
        "answer": answer,
        "timestamp": timestamp
    })
    save_data(data)
    
    # Send response
    update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)

# Error handler
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Update {update} caused error {context.error}")
    if update:
        update.message.reply_text("Ой, что-то сломалось! Попробуй снова.")

# Main function
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("history", history))
    dp.add_handler(CommandHandler("clear", clear))
    
    # Messages
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Error handling
    dp.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Bot started")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
