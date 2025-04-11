import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import json
from googlesearch import search  # Новая библиотека для поиска

# Токен от @BotFather
TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"

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
    try:
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения данных: {e}")

# Функция для поиска ответа в интернете через googlesearch-python
def search_online(query):
    try:
        # Получаем первый результат поиска
        results = list(search(query, num_results=1, lang="ru"))
        if results:
            return results[0]  # Возвращаем URL или описание
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

    # Проверяем историю
    for entry in data["history"]:
        if entry["question"] == user_message:
            update.message.reply_text(f"Я уже знаю ответ: {entry['answer']}")
            return

    # Ищем новый ответ
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
