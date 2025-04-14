import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
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

# Telegram Bot Token (замените на ваш токен от BotFather)
TELEGRAM_TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"

# Hugging Face Token (замените на ваш токен от Hugging Face)
HF_TOKEN = "YOUR_HUGGINGFACE_TOKEN_HERE"

# Загружаем модель и токенизатор
model_name = "mistralai/Mixtral-8x7B-Instruct-v0.1"  # Можно заменить на "distilgpt2" для легкой модели
try:
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=HF_TOKEN, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, use_auth_token=HF_TOKEN, torch_dtype=torch.float16, device_map="auto")
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    exit(1)

# Словарь для хранения истории чата по chat_id
chat_histories = {}

def format_input(user_input, is_question=False):
    """Форматирует ввод пользователя для модели."""
    if is_question:
        return f"[Вопрос] {user_input} [Ответ]"
    return f"[Пользователь] {user_input} [Бот]"

def clean_response(response):
    """Очищает ответ от лишних символов и артефактов."""
    response = re.sub(r"\[Бот\].*?$", "", response, flags=re.DOTALL)
    response = re.sub(r"\[.*?\]", "", response)
    return response.strip()

async def get_response(user_input, chat_id, max_history_len=5):
    """Генерирует ответ на основе ввода и истории."""
    if not user_input.strip():
        return "Пожалуйста, отправьте сообщение."

    # Определяем, является ли ввод вопросом
    is_question = "?" in user_input or user_input.lower().startswith(("что", "как", "почему", "кто", "где", "когда"))

    # Форматируем текущий ввод
    formatted_input = format_input(user_input, is_question)

    # Получаем историю чата для данного chat_id
    history = chat_histories.get(chat_id, [])

    # Обрезаем историю, чтобы не превысить лимит
    if len(history) > max_history_len:
        history = history[-max_history_len:]

    # Формируем полный контекст
    context = "\n".join(history + [formatted_input])

    # Кодируем контекст
    input_ids = tokenizer.encode(context, return_tensors="pt").to(model.device)

    try:
        # Генерируем ответ
        output_ids = model.generate(
            input_ids,
            max_new_tokens=200,
            pad_token_id=tokenizer.eos_token_id,
            no_repeat_ngram_size=3,
            do_sample=True,
            top_k=50,
            top_p=0.9,
            temperature=0.7,
            early_stopping=True
        )

        # Декодируем только новый текст
        generated_text = tokenizer.decode(output_ids[0, input_ids.shape[-1]:], skip_special_tokens=True)
        response = clean_response(generated_text)

        # Обновляем историю
        history.append(f"[Пользователь] {user_input} [Бот] {response}")
        chat_histories[chat_id] = history

        return response

    except Exception as e:
        return f"Ошибка при генерации ответа: {str(e)}"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я чат-бот, готов ответить на твои вопросы или поболтать. "
        "Используй /clear, чтобы очистить историю чата."
    )

# Обработчик команды /clear
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    chat_histories[chat_id] = []
    await update.message.reply_text("История чата очищена!")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_input = update.message.text
    response = await get_response(user_input, chat_id)
    await update.message.reply_text(response)

def main():
    """Запускает бота."""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
