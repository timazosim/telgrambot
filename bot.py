import os
import json
import time
import random
from datetime import datetime
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
from pyowm import OWM
import wikipediaapi
import pyjokes
from randomfacts import RandomFacts
import emoji
import nltk
import logging

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена
TOKEN = os.getenv("7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574")
if not TOKEN:
    logger.error("Токен не задан! Установите TELEGRAM_TOKEN в переменных окружения.")
    raise ValueError("Токен не установлен. Пожалуйста, задайте TELEGRAM_TOKEN.")

# Ключ для OpenWeatherMap
OWM_API_KEY = "your_openweathermap_key_here"  # Замените на ваш ключ с openweathermap.org
owm = OWM(OWM_API_KEY) if OWM_API_KEY != "your_openweathermap_key_here" else None

# Конфигурация
DATA_FILE = "bot_data.json"
RATE_LIMIT = 10  # Максимум сообщений в минуту на пользователя
user_timestamps = {}

# Предустановленные ответы
FALLBACK_RESPONSES = [
    "Ого, интересный вопрос! Давай попробуем найти ответ? 😊",
    "Хм, ты меня озадачил! Может, уточнишь? 🤔",
    "Не уверен, но могу рассказать факт или шутку! 😄",
    "Кажется, мой интернет-радар спит! Попробуем ещё раз? 🚀",
]

# Настройка Википедии
wiki = wikipediaapi.Wikipedia("ru")

# Настройка RandomFacts
facts = RandomFacts()

# Настройка NLTK
nltk.download('punkt', quiet=True)
nltk.download('vader_lexicon', quiet=True)

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

# Веб-парсинг для поиска
def search_web(query):
    try:
        url = f"https://www.qwant.com/?q={query}&t=web"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("div", class_="result__body")
        if results:
            return results[0].get_text(strip=True)[:200]  # Первые 200 символов
        return None
    except Exception as e:
        logger.error(f"Ошибка веб-поиска: {e}")
        return None

# Поиск в Википедии
def search_wikipedia(query):
    try:
        page = wiki.page(query)
        if page.exists():
            return page.summary[:200]  # Первые 200 символов
        return None
    except Exception as e:
        logger.error(f"Ошибка Википедии: {e}")
        return None

# Получение погоды
def get_weather(city):
    if not owm:
        return "Погода недоступна: задайте OWM_API_KEY."
    try:
        mgr = owm.weather_manager()
        observation = mgr.weather_at_place(city)
        w = observation.weather
        temp = w.temperature("celsius")["temp"]
        status = w.detailed_status
        return f"Погода в {city}: {temp}°C, {status} {emoji.emojize(':sun:') if 'sun' in status else emoji.emojize(':cloud:')}"
    except Exception as e:
        logger.error(f"Ошибка погоды: {e}")
        return f"Не удалось найти погоду для {city}."

# Анализ настроения
def analyze_sentiment(text):
    try:
        blob = TextBlob(text)
        sentiment = blob.sentiment.polarity
        if sentiment > 0.1:
            return "позитивный 😊", sentiment
        elif sentiment < -0.1:
            return "негативный 😔", sentiment
        else:
            return "нейтральный 😐", sentiment
    except Exception as e:
        logger.error(f"Ошибка анализа настроения: {e}")
        return "неизвестный 🤷", 0

# Перевод текста
def translate_text(text, to_lang="ru"):
    try:
        blob = TextBlob(text)
        return str(blob.translate(to=to_lang))
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        return text

# Получение шутки
def get_joke():
    try:
        return pyjokes.get_joke(language="en", category="neutral")
    except Exception as e:
        logger.error(f"Ошибка шутки: {e}")
        return "Не могу найти шутку, но вот улыбка: 😄"

# Получение факта
def get_fact():
    try:
        return facts.get_fact()
    except Exception as e:
        logger.error(f"Ошибка факта: {e}")
        return "Интересный факт: Земля круглая! 🌍"

# Извлечение ключевых слов
def extract_keywords(text):
    try:
        tokens = nltk.word_tokenize(text.lower())
        return [word for word in tokens if word.isalnum() and len(word) > 3]
    except Exception as e:
        logger.error(f"Ошибка извлечения ключевых слов: {e}")
        return [text.lower()]

# Команда /start
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        emoji.emojize(
            f"Привет, {user.first_name}! Я супер-бот! :robot:\n"
            "Могу искать в интернете, показывать погоду, шутить, находить факты и анализировать настроение.\n"
            "Команды:\n"
            "/start - Приветствие\n"
            "/weather <город> - Погода\n"
            "/joke - Шутка\n"
            "/fact - Случайный факт\n"
            "/history - История вопросов\n"
            "/clear - Очистить историю\n"
            "Просто задай вопрос, и я найду ответ! :mag:"
        ),
        parse_mode=ParseMode.MARKDOWN
    )

# Команда /weather
def weather(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not check_rate_limit(user_id):
        update.message.reply_text(emoji.emojize("Слишком много сообщений! Подожди минутку. :hourglass:"), parse_mode=ParseMode.MARKDOWN)
        return
    
    city = " ".join(context.args) if context.args else "Moscow"
    result = get_weather(city)
    update.message.reply_text(emoji.emojize(result), parse_mode=ParseMode.MARKDOWN)

# Команда /joke
def joke(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not check_rate_limit(user_id):
        update.message.reply_text(emoji.emojize("Слишком много сообщений! Подожди минутку. :hourglass:"), parse_mode=ParseMode.MARKDOWN)
        return
    
    joke_text = get_joke()
    update.message.reply_text(emoji.emojize(f"Шутка: {joke_text} :laughing:"), parse_mode=ParseMode.MARKDOWN)

# Команда /fact
def fact(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if not check_rate_limit(user_id):
        update.message.reply_text(emoji.emojize("Слишком много сообщений! Подожди минутку. :hourglass:"), parse_mode=ParseMode.MARKDOWN)
        return
    
    fact_text = get_fact()
    update.message.reply_text(emoji.emojize(f"Факт: {fact_text} :bulb:"), parse_mode=ParseMode.MARKDOWN)

# Команда /history
def history(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id not in data["users"] or not data["users"][user_id]:
        update.message.reply_text(emoji.emojize("История пуста! Задай мне вопрос. :open_book:"), parse_mode=ParseMode.MARKDOWN)
        return
    
    response = emoji.emojize("*Твоя история вопросов:*\n:history:")
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
        update.message.reply_text(emoji.emojize("История очищена! :broom:"), parse_mode=ParseMode.MARKDOWN)
    else:
        update.message.reply_text(emoji.emojize("У тебя пока нет истории. :open_book:"), parse_mode=ParseMode.MARKDOWN)

# Обработка сообщений
def handle_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user_message = update.message.text.strip()
    
    if not check_rate_limit(user_id):
        update.message.reply_text(emoji.emojize("Слишком много сообщений! Подожди минутку. :hourglass:"), parse_mode=ParseMode.MARKDOWN)
        return
    
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = []
    
    # Проверка истории
    for entry in data["users"][user_id]:
        if entry["question"].lower() == user_message.lower():
            update.message.reply_text(emoji.emojize(f"Я уже отвечал: {entry['answer']} :repeat:"), parse_mode=ParseMode.MARKDOWN)
            return
    
    # Перевод, если текст не на русском
    translated_message = translate_text(user_message, to_lang="ru")
    if translated_message != user_message:
        logger.info(f"Переведено: {user_message} -> {translated_message}")
    
    # Извлечение ключевых слов
    keywords = extract_keywords(translated_message)
    query = " ".join(keywords) if keywords else translated_message
    
    # Анализ настроения
    sentiment, score = analyze_sentiment(user_message)
    sentiment_response = f"Настроение твоего вопроса: {sentiment} (оценка: {score:.2f})"
    
    # Поиск ответа
    answer = None
    source = None
    
    # 1. Википедия
    answer = search_wikipedia(query)
    if answer:
        source = "Википедия"
        logger.info("Ответ найден в Википедии")
    
    # 2. Веб-поиск
    if not answer:
        answer = search_web(query)
        if answer:
            source = "Интернет"
            logger.info("Ответ найден в интернете")
    
    # 3. Факт или шутка
    if not answer:
        if random.random() < 0.5:
            answer = get_fact()
            source = "Факт"
        else:
            answer = get_joke()
            source = "Шутка"
    
    # Форматирование ответа
    final_answer = f"{sentiment_response}\n*{source}:* {answer}"
    
    # Сохранение в историю
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["users"][user_id].append({
        "question": user_message,
        "answer": final_answer,
        "timestamp": timestamp
    })
    save_data(data)
    
    # Отправка ответа
    update.message.reply_text(emoji.emojize(final_answer), parse_mode=ParseMode.MARKDOWN)

# Обработчик ошибок
def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка: {context.error}")
    if update and update.message:
        update.message.reply_text(emoji.emojize("Ой, что-то пошло не так! Попробуй снова. :warning:"), parse_mode=ParseMode.MARKDOWN)

# Основная функция
def main():
    try:
        logger.info("Запуск бота...")
        updater = Updater(TOKEN, use_context=True)
        dp = updater.dispatcher
        
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("weather", weather))
        dp.add_handler(CommandHandler("joke", joke))
        dp.add_handler(CommandHandler("fact", fact))
        dp.add_handler(CommandHandler("history", history))
        dp.add_handler(CommandHandler("clear", clear))
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
