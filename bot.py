import logging
import asyncio
import aiosqlite
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Налаштування
MODEL_NAME = "malteos/gpt2-uk"  # Відкрита українська GPT-2 модель
MAX_CONTEXT_TOKENS = 400
DB_PATH = "memory.db"

# Логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Завантаження моделі
print("Завантаження моделі...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
print("Модель готова.")

# Створення таблиці в базі
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                user_id TEXT,
                fact TEXT
            )
        ''')
        await db.commit()

# Завантажити факти користувача
async def load_user_data(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fact FROM memory WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# Додати факт
async def save_fact(user_id, fact):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO memory (user_id, fact) VALUES (?, ?)", (user_id, fact))
        await db.commit()

# Команда /старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Я україномовний GPT-бот. Пиши щось — і я відповім!")

# Команда /хто_я
async def who_am_i(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    facts = await load_user_data(user_id)
    if facts:
        text = "Ось що я про тебе пам’ятаю:\n\n" + "\n".join(f"• {f}" for f in facts)
    else:
        text = "Поки що я нічого про тебе не пам’ятаю."
    await update.message.reply_text(text)

# Генерація відповіді
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_input = update.message.text

    memory = await load_user_data(user_id)
    prompt = "\n".join(memory + [user_input])[-MAX_CONTEXT_TOKENS:]
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=100, pad_token_id=tokenizer.eos_token_id)

    reply = tokenizer.decode(output[0], skip_special_tokens=True)[len(prompt):].strip()

    # Проста евристика для запам’ятовування фактів
    if any(word in user_input.lower() for word in ["я", "мене звати", "мій", "я люблю"]):
        await save_fact(user_id, user_input)

    await update.message.reply_text(reply or "Не маю що відповісти.")

# Головна функція
async def main():
    await init_db()

    app = ApplicationBuilder().token("<7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574>").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("хто_я", who_am_i))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Бот запущено.")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
