import os
import json
import time
from datetime import datetime
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import requests
import wikipedia
import pyjokes
from googlesearch import search
import logging
import random

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена
TOKEN = os.getenv("7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574")
if not TOKEN:
    TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"  # Замените на ваш токен
    logger.warning("TELEGRAM_TOKEN не найден в переменных окружения. Используется токен из кода (небезопасно).")

if not TOKEN:
    logger.error("Токен не задан! Установите TELEGRAM_TOKEN в переменных окружения или укажите в коде.")
    raise ValueError("Токен не установлен")

# Конфигурация
DATA_FILE = "bot_data.json"
RATE_LIMIT = 10  # Максимум сообщений в минуту на пользователя
user_timestamps = {}

# Предустановленные ответы
FALLBACK_RESPONSES = [
    "Хм, интересный вопрос! Не нашёл ответа, давай попробуем переформулировать? 😊",
    "Кажется, интернет молчит! Уточни детали или спроси про шутку!",
    "Ого, ты меня озадачил! Может, я найду новости по этой теме?",
    "Упс, мои источники иссякли! 😄 Хочешь шутку вместо ответа?",
]

# Настройка Википедии
wikipedia.set_lang("ru")

# Настройка переводчика
translator = Translator()

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

# Поиск через Google Search
def search_google(query):
    try:
        for result in search(query, num_results=1, lang="ru", pause=2.0):
            return result
        return None
    except Exception as e:
        logger.error(f"Ошибка Google Search: {e}")
        return None

# Поиск новостей через NewsAPI
def search_newsapi(query):
    if NEWSAPI_KEY == "your_newsapi_key_here":
        return None
    try:
        url = "https://newsapi.org/v2/everything"
        params = {"q": query, "apiKey": NEWSAPI_KEY, "language": "ru", "pageSize": 1}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("articles"):
            return data["articles"][0].get("description", None)
        return None
    except Exception as e:
        logger.error(f"Ошибка NewsAPI: {e}")
        return None

# Поиск в Википедии
def search_wikipedia(query):
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        return f"Уточни, пожалуйста, я нашёл несколько вариантов: {', '.join(e.options[:3])}"
    except wikipedia.exceptions.PageError:
        return None
    except Exception as e:
        logger.error(f"Ошибка Википедии: {e}")
        return None

# Перевод текста
def translate_text(text, to_lang="ru"):
    try:
        translated = translator.translate(text, dest=to_lang)
        return translated.text
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        return text

# Получение шутки
def get_joke():
    try:
        joke = pyjokes.get_joke(language="en", category="neutral")
        return translate_text(joke, to_lang="ru")
    except Exception as e:
        logger.error(f"Ошибка шутки: {e}")
        return "Не могу найти шутку, но вот улыбка: 😄"

# Получение предустановленного ответа
def get_fallback_response():
    return random.choice(FALLBACK_RESPONSES)

# Команда /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}! Я твой умный бот! 😄 Ищу информацию в интернете, рассказываю новости, "
        "шучу и перевожу. Задавай вопрос или используй команды: /start, /history, /clear, /joke",
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /history
def history(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data["users"] or not data["users"][user_id]:
        update.message.reply_text("История пуста! Задай мне вопрос.", parse_mode=ParseMode.MARKDOWN)
        return
    
    response = "*Твоя история вопросов:*\n"
    for entry in data["users"][user_id][-5:]:
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
        update.message.reply_text("У тебя пока нет истории.", parse_mode=ParseMode.MARKDOWN)

# Команда /joke
def joke(update: Update, context: CallbackContext):
    joke_text = get_joke()
    update.message.reply_text(f"Вот тебе шутка: {joke_text}", parse_mode=ParseMode.MARKDOWN)

# Обработка сообщений
def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_message = update.message.text.strip()
    
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
    
    # Перевод вопроса
    translated_message = translate_text(user_message, to_lang="ru")
    if translated_message != user_message:
        logger.info(f"Переведено: {user_message} -> {translated_message}")
    
    # Поиск ответа
    answer = None
    source = None
    
    # 1. Google Search
    answer = search_google(translated_message)
    if answer:
        source = "Google"
        logger.info("Ответ найден через Google Search")
    
    # 2. NewsAPI
    if not answer:
        answer = search_newsapi(translated_message)
        if answer:
            source = "Новости"
            logger.info("Ответ найден через NewsAPI")
    
    # 3. Википедия
    if not answer:
        answer = search_wikipedia(translated_message)
        if answer:
            source = "Википедия"
            logger.info("Ответ найден в Википедии")
    
    # 4. Шутка или предустановленный ответ
    if not answer:
        if random.random() < 0.5:
            answer = f"Не нашёл информацию, но вот шутка: {get_joke()}"
            source = "Шутка"
        else:
            answer = get_fallback_response()
            source = "Предустановленный ответ"
    
    # Форматирование ответа
    final_answer = f"*{source}:* {answer}"
    
    # Сохранение в историю
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["users"][user_id].append({
        "question": user_message,
        "answer": final_answer,
        "timestamp": timestamp
    })
    save_data(data)
    
    # Отправка ответа
    update.message.reply_text(final_answer, parse_mode=ParseMode.MARKDOWN)

# Обработчик ошибок
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка: {context.error}")
    if update and update.message:
        update.message.reply_text("Ой, что-то пошло не так! Попробуй снова.", parse_mode=ParseMode.MARKDOWN)

# Основная функция
def main():
    try:
        logger.info("Запуск бота...")
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("history", history))
        dp.add_handler(CommandHandler("clear", clear))
        dp.add_handler(CommandHandler("joke", joke))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        dp.add_error_handler(error_handler)
        
        logger.info("Бот успешно запущен")
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    main()
