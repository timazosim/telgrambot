import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import json
from serpapi import GoogleSearch  # Новая библиотека для поиска

# Токен от @BotFather
TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"

# Ключ API от SerpApi (замени на свой!)
SERPAPI_KEY = "a1b2c3d4e5f6g7h8i9j0"

# Название файла для хранения данных
DATA_FILE = "bot_data.json"

# Функция для загрузки данных из файла
def load_data():
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"history": []}

# Функция для сохранения данных в файл
def save_data(data):
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)

# Функция для поиска ответа в интернете через SerpApi
def search_online(query):
    try:
        params = {
            "q": query,  # Запрос
            "api_key": SERPAPI_KEY,  # Твой ключ API
            "num": 1  # Ограничим одним результатом
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Проверяем, есть ли органические результаты
        if "organic_results" in results and len(results["organic_results"]) > 0:
            return results["organic_results"][0].get("snippet", "Нет краткого ответа.")
        return "К сожалению, я не нашёл ответа. Попробуй другой вопрос!"
    except Exception as e:
        return f"Ошибка при поиске: {str(e)}. Попробуй ещё раз!"

# Команда /start
def start(update, context):
    update.message.reply_text("Привет! Я твой умный бот. Задавай вопросы, я найду ответы и запомню их!")

# Команда /history
def history(update, context):
    data = load_data()
    if not data["history"]:
        update.message.reply_text("История пуста!")
        return
    response = "Вот твои вопросы и ответы:\n"
    for entry in data["history"]:
        response += f"Вопрос: {entry['question']}\nОтвет: {entry['answer']}\n\n"
    update.message.reply_text(response)

# Обработка текстовых сообщений
def handle_message(update, context):
    user_message = update.message.text.lower()
    data = load_data()

    for entry in data["history"]:
        if entry["question"] == user_message:
            update.message.reply_text(f"Я уже знаю ответ: {entry['answer']}")
            return

    answer = search_online(user_message)
    data["history"].append({"question": user_message, "answer": answer})
    save_data(data)
    update.message.reply_text(answer)

# Главная функция
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("history", history))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
