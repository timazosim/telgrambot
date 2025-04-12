import os
import json
import time
from datetime import datetime
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import requests
import logging

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена
TOKEN = ("7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574")

# Проверка токена
if not TOKEN:
    logger.error("TELEGRAM_TOKEN не найден в переменных окружения! Убедитесь, что файл .env существует и содержит TELEGRAM_TOKEN.")
    raise ValueError("TELEGRAM_TOKEN не установлен")

# Конфигурация
DATA_FILE = "bot_data.json"
RATE_LIMIT = 10  # Максимум сообщений в минуту на пользователя
user_timestamps = {}

# Предустановленные ответы для случаев, когда поиск не дал результатов
FALLBACK_RESPONSES = [
    "Хм, интересный вопрос! Не нашёл точного ответа, но давай попробуем переформулировать? 😊",
    "Кажется, это загадка! Может, уточнишь детали?",
    "Ого, ты меня озадачил! Давай попробуем ещё раз!",
]

# Загрузка данных
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logger.info("Файл данных не найден, создаём новый.")
        return {"users": {}}
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        return {"users": {}}

# Сохранение данных
def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

# Проверка лимита сообщений
def check_rate_limit(user_id):
    now = time.time()
    if user_id not in user_timestamps:
        user_timestamps[user_id] = []
    user_timestamps[user_id] = [t for t in user_timestamps[user_id] if now - t < 60]
    if len(user_timestamps[user_id]) >= RATE_LIMIT:
        return False
    user_timestamps[user_id].append(now)
    return True

# Поиск с использованием DuckDuckGo API
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

# Получение предустановленного ответа
def get_fallback_response():
    from random import choice
    return choice(FALLBACK_RESPONSES)

# Команда /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}! Я твой умный бот. Задавай вопросы, я постараюсь ответить! 😄\n"
        "Команды: /start, /history, /clear",
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /history
def history(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data["users"] or not data["users"][user_id]:
        update.message.reply_text("История пуста! Задай мне вопрос, чтобы начать.", parse_mode=ParseMode.MARKDOWN)
        return
    
    response = "*Твоя история вопросов:*\n"
    for entry in data["users"][user_id][-5:]:  # Показываем последние 5 записей
        timestamp = entry.get("timestamp", "Неизвестно")
        question = entry["question"]
        answer = entry["answer"]
        response += f"_{timestamp}_\n*Вопрос:* {question}\n*Ответ:* {answer}\n\n"
    
    update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

# Команда /clear
def clear(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id in data["users"]:
        data["users"][user_id] = []
        save_data(data)
        update.message.reply_text("История очищена!", parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text("У тебя пока нет истории для очистки.", parse_mode=ParseMode.MARKDOWN)

# Обработка текстовых сообщений
def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_message = update.message.text.strip()
    
    # Проверка лимита сообщений
    if not check_rate_limit(user_id):
        update.message.reply_text("Слишком много сообщений! Подожди минутку.", parse_mode=ParseMode.MARKDOWN)
        return
    
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = []
    
    # Проверка истории
    for entry in data["users"][user_id]:
        if entry["question"].lower() == user_message.lower():
            update.message.reply_text(f"Я уже отвечал: {entry['answer']}", parse_mode=ParseMode.MARKDOWN)
            return
    
    # Поиск ответа
    answer = search_online(user_message)
    
    # Использование предустановленного ответа, если поиск не удался
    if not answer:
        answer = get_fallback_response()
    
    # Сохранение в историю
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["users"][user_id].append({
        "question": user_message,
        "answer": answer,
        "timestamp": timestamp
    })
    save_data(data)
    
    # Отправка ответа
    update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)

# Обработчик ошибок
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
    if update and update.message:
        update.message.reply_text("Ой, что-то пошло не так! Попробуй снова.", parse_mode=ParseMode.MARKDOWN)

# Основная функция
def main():
    try:
        logger.info("Запуск бота...")
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        
        # Команды
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("history", history))
        dp.add_handler(CommandHandler("clear", clear))
        
        # Обработка сообщений
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        
        # Обработчик ошибок
        dp.add_error_handler(error_handler)
        
        # Запуск бота
        logger.info("Бот успешно запущен")
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    main()
