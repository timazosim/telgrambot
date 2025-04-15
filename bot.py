import torch
import re
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import asyncio
import logging

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token (замените на ваш токен от BotFather)
TELEGRAM_TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"

# Словарь для хранения истории чата по chat_id
chat_histories = {}

def format_input(user_input, is_question=False):
    """Форматирует ввод пользователя."""
    if is_question:
        return f"[Вопрос] {user_input} [Ответ]"
    return f"[Пользователь] {user_input} [Бот]"

def clean_response(response):
    """Очищает ответ от лишних символов."""
    response = re.sub(r"\[Бот\].*?$", "", response, flags=re.DOTALL)
    response = re.sub(r"\[.*?\]", "", response)
    return response.strip()

async def get_response(user_input, chat_id, max_history_len=5):
    """Генерирует ответ на основе ввода и истории."""
    if not user_input.strip():
        return "Пожалуйста, отправьте сообщение."

    logger.info(f"Обработка ввода: {user_input}")
    # Определяем, является ли ввод вопросом
    is_question = "?" in user_input or user_input.lower().startswith(("что", "как", "почему", "кто", "где", "когда"))

    # Форматируем текущий ввод
    formatted_input = format_input(user_input, is_question)

    # Получаем историю чата для данного chat_id
    history = chat_histories.get(chat_id, [])

    # Обрезаем историю, чтобы не превысить лимит
    if len(history) > max_history_len:
        history = history[-max_history_len:]

    # Формируем ответ (заглушка вместо модели)
    try:
        # Здесь должна быть логика генерации ответа, но без Hugging Face используем эхо
        response = f"Эхо: {user_input}"  # Замените на вызов другой модели или API, если нужно

        # Обновляем историю
        history.append(f"[Пользователь] {user_input} [Бот] {response}")
        chat_histories[chat_id] = history

        logger.info(f"Сгенерирован ответ: {response}")
        return response

    except Exception as e:
        logger.error(f"Ошибка при генерации ответа: {e}")
        return f"Ошибка при генерации ответа: {str(e)}"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Получена команда /start")
    await update.message.reply_text(
        "Привет! Я чат-бот, готов ответить на твои вопросы или поболтать. "
        "Используй /clear, чтобы очистить историю чата."
    )

# Обработчик команды /clear
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    logger.info(f"История очищена для chat_id: {chat_id}")
    await update.message.reply_text("История чата очищена!")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_input = update.message.text
    response = await get_response(user_input, chat_id)
    await update.message.reply_text(response)

def main():
    """Запускает бота."""
    try:
        logger.info("Инициализация бота...")
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("clear", clear))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Запускаем бота
        logger.info("Бот запущен, начало polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    main()
