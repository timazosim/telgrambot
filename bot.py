import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import requests
import logging

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
pdater = Updater(TOKEN, use_context=True)
TOKEN = os.getenv("7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574")
DATA_FILE = "bot_data.json"

# Rate limiting configuration
RATE_LIMIT = 10  # Max messages per minute per user
user_timestamps = {}

# Predefined fallback responses
FALLBACK_RESPONSES = [
    "Хм, это интересный вопрос! Дай мне секунду подумать... 😊",
    "К сожалению, у меня нет точного ответа, но я могу предложить поискать это вместе!",
    "Ого, ты меня озадачил! Может, переформулируем вопрос?",
]

# Load conversation data
def load_data():
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"users": {}}
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        return {"users": {}}

# Save conversation data
def save_data(data):
    try:
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

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

# Search online using DuckDuckGo API
def search_online(query):
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "t": "telegram_bot"}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("Abstract"):
            return data["Abstract"]
        elif data.get("RelatedTopics"):
            return data["RelatedTopics"][0].get("Text", "Ничего не нашёл.")
        return None
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return None

# Generate a fallback response
def get_fallback_response():
    from random import choice
    return choice(FALLBACK_RESPONSES)

# Command: /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}! Я твой умный бот. Задавай вопросы, я попробую ответить или найти ответ! 😄\n"
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
    
    # Check history
    for entry in data["users"][user_id]:
        if entry["question"].lower() == user_message.lower():
            update.message.reply_text(f"Я уже отвечал: {entry['answer']}")
            return
    
    # Try online search
    answer = search_online(user_message)
    
    # Fallback to predefined response if search fails
    if not answer:
        answer = get_fallback_response()
    
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
    logger.info("Бот запущен")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
