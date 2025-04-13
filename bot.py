import os
import json
import time
import random
from datetime import datetime
from telegram import Update, ParseMode
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
from pyowm import OWM
import wikipediaapi
import pyjokes
import emoji
import nltk
import logging
import re

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена
TOKEN = os.getenv("7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574")
if not TOKEN:
    TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"  # Временный токен
    logger.warning("TELEGRAM_TOKEN не найден в переменных окружения. Используется токен из кода (небезопасно).")

if not TOKEN:
    logger.error("Токен не задан! Установите TELEGRAM_TOKEN в переменных окружения или укажите в коде.")
    raise ValueError("Токен не установлен.")

# Ключ для OpenWeatherMap
OWM_API_KEY = "your_openweathermap_key_here"  # Замените на ваш ключ
owm = OWM(OWM_API_KEY) if OWM_API_KEY != "your_openweathermap_key_here" else None

# Конфигурация
DATA_FILE = "bot_data.json"
RATE_LIMIT = 10
user_timestamps = {}

# Предустановленные ответы
FALLBACK_RESPONSES = [
    "Ого, интересный запрос! Давай попробуем найти ответ? 😊",
    "Хм, ты меня озадачил! Может, уточнишь? 🤔",
    "Не уверен, но могу рассказать факт или шутку! 😄",
    "Кажется, мой интернет-радар спит! Попробуем ещё раз? 🚀",
]

# Настройка Википедии
wiki = wikipediaapi.Wikipedia("ua")

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

# Веб-парсинг
def search_web(query):
    try:
        url = f"https://www.qwant.com/?q={query}&t=web"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("div", class_="result__body")
        if results:
            return results[0].get_text(strip=True)[:200]
        return None
    except Exception as e:
        logger.error(f"Ошибка веб-поиска: {e}")
        return None

# Поиск в Википедии
def search_wikipedia(query):
    try:
        page = wiki.page(query)
        if page.exists():
            return page.summary[:200]
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

# Классификация намерения
def classify_intent(text):
    text_lower = text.lower()
    
    # Погода
    if re.search(r"\b(погода|температура|градус|прогноз)\b", text_lower):
        # Извлечение города
        tokens = nltk.word_tokenize(text_lower)
        cities = [t.capitalize() for t in tokens if t.isalpha() and t not in ["погода", "температура", "какая", "в"]]
        city = cities[0] if cities else "Moscow"
        return "weather", city
    
    # Шутка
    if re.search(r"\b(шутка|посмеяться|анекдот|смешно)\b", text_lower):
        return "joke", None
    
    # Факт
    if re.search(r"\b(факт|интересно|знал)\b", text_lower):
        return "fact", None
    
    # История
    if re.search(r"\b(история|прошлые|вопросы)\b", text_lower):
        return "history", None
    
    # Очистка истории
    if re.search(r"\b(очистить|удалить|историю)\b", text_lower):
        return "clear", None
    
    # Вопрос (поиск)
    if re.search(r"\b(что|кто|где|когда|почему|как|зачем)\b", text_lower):
        return "search", text_lower
    
    # Общий поиск
    return "search", text_lower

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
    
    # Приветствие для новых пользователей
    if not data["users"][user_id] and "привет" in user_message.lower():
        update.message.reply_text(
            emoji.emojize(
                f"Привет! Я умный бот! :robot:\n"
                "Спрашивай о погоде, фактах, шути, ищи информацию — я всё умею!\n"
                "Например: 'Какая погода в Москве?', 'Расскажи шутку', 'Что такое Python?'"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Проверка истории
    for entry in data["users"][user_id]:
        if entry["question"].lower() == user_message.lower():
            update.message.reply_text(emoji.emojize(f"Я уже отвечал: {entry['answer']} :repeat:"), parse_mode=ParseMode.MARKDOWN)
            return
    
    # Перевод
    translated_message = translate_text(user_message, to_lang="ru")
    if translated_message != user_message:
        logger.info(f"Переведено: {user_message} -> {translated_message}")
    
    # Ключевые слова
    keywords = extract_keywords(translated_message)
    query = " ".join(keywords) if keywords else translated_message
    
    # Анализ настроения
    sentiment, score = analyze_sentiment(user_message)
    sentiment_response = f"Настроение твоего запроса: {sentiment} (оценка: {score:.2f})"
    
    # Классификация намерения
    intent, param = classify_intent(translated_message)
    
    # Обработка намерения
    answer = None
    source = None
    
    if intent == "weather":
        answer = get_weather(param)
        source = "Погода"
        logger.info(f"Запрос погоды: {param}")
    
    elif intent == "joke":
        answer = get_joke()
        source = "Шутка"
        logger.info("Запрос шутки")
    
    elif intent == "fact":
        answer = get_fact()
        source = "Факт"
        logger.info("Запрос факта")
    
    elif intent == "history":
        if user_id not in data["users"] or not data["users"][user_id]:
            answer = "История пуста! Задай мне вопрос."
            source = "История"
        else:
            response = emoji.emojize("*Твоя история вопросов:*\n:history:")
            for entry in data["users"][user_id][-5:]:
                timestamp = entry.get("timestamp", "Неизвестно")
                question = entry["question"]
                ans = entry["answer"]
                response += f"_{timestamp}_\n*Вопрос:* {question}\n*Ответ:* {ans}\n\n"
            answer = response
            source = "История"
        logger.info("Запрос истории")
    
    elif intent == "clear":
        if user_id in data["users"]:
            data["users"][user_id] = []
            save_data(data)
            answer = "История очищена!"
            source = "Очистка"
        else:
            answer = "У тебя пока нет истории."
            source = "Очистка"
        logger.info("Запрос очистки истории")
    
    elif intent == "search":
        # Википедия
        answer = search_wikipedia(query)
        if answer:
            source = "Википедия"
            logger.info("Ответ найден в Википедии")
        
        # Веб-поиск
        if not answer:
            answer = search_web(query)
            if answer:
                source = "Интернет"
                logger.info("Ответ найден в интернете")
        
        # Факт или шутка
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
