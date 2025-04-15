import re
import logging
import os
import sys
import atexit
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

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

# Простая база знаний для ответов
KNOWLEDGE_BASE = {
    r"(?i)что такое (.*)": lambda match: f"{match.group(1).capitalize()} — это общее понятие. Например, если вы спросили про 'Python', это язык программирования.",
    r"(?i)как (.*)": lambda match: f"Чтобы {match.group(1).lower()}, нужно уточнить детали. Например, 'как программировать' — начните с изучения основ языка.",
    r"(?i)почему (.*)": lambda match: f"Причина, почему {match.group(1).lower()}, может зависеть от контекста. Уточните, и я помогу!",
    r"(?i)кто (.*)": lambda match: f"Кто {match.group(1).lower()}? Это может быть человек, персонаж или что-то другое. Дайте больше информации.",
    r"(?i)где (.*)": lambda match: f"Где {match.group(1).lower()}? Это может быть место или абстрактное понятие. Уточните, пожалуйста.",
    r"(?i)когда (.*)": lambda match: f"Когда {match.group(1).lower()}? Это зависит от события. Расскажите больше.",
}

# Проверка на дублирующийся запуск
LOCK_FILE = "bot.lock"

def create_lock():
    if os.path.exists(LOCK_FILE):
        logger.error("Another instance of the bot is already running.")
        sys.exit(1)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(remove_lock)

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

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
    """Генерирует ответ на основе ввода и правил."""
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

    try:
        # Проверяем ввод на соответствие шаблонам в базе знаний
        response = None
        for pattern, response_func in KNOWLEDGE_BASE.items():
            match = re.match(pattern, user_input)
            if match:
                response = response_func(match)
                break

        # Если не найдено совпадение, даём общий ответ
        if not response:
            response = "Интересный вопрос! Уточните детали, и я постараюсь ответить точнее."

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
    create_lock()
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
