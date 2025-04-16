import logging
import aiosqlite
import asyncio
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# === GPT-модель ===
MODEL_NAME = "blinoff/ukrainian-gpt2"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)

# === Персональність бота ===
BOT_PERSONALITY = (
    "Ти — дружній, уважний і трохи жартівливий україномовний бот. "
    "Ти пам’ятаєш факти про співрозмовника й намагаєшся будувати діалог природно.\n"
)

MAX_CONTEXT_TOKENS = 400
DB_FILE = "bot_memory.db"

# === Ініціалізація бази даних ===
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                user_id TEXT PRIMARY KEY,
                context TEXT,
                memory TEXT
            )
        """)
        await db.commit()

# === Завантаження даних користувача з БД ===
async def load_user_data(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT context, memory FROM user_data WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                context = row[0].split("||") if row[0] else []
                memory = row[1].split("||") if row[1] else []
                return context, memory
            else:
                return [], []

# === Збереження даних користувача в БД ===
async def save_user_data(user_id, context, memory):
    context_str = "||".join(context)
    memory_str = "||".join(memory)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO user_data (user_id, context, memory)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            context=excluded.context,
            memory=excluded.memory
        """, (user_id, context_str, memory_str))
        await db.commit()

# === Оновлення пам’яті ===
def update_memory(memory, user_input):
    if "мене звати" in user_input.lower():
        name = user_input.split("мене звати")[-1].strip().split()[0]
        memory.append(f"Ім’я користувача — {name}.")
    elif "я люблю" in user_input.lower():
        hobby = user_input.split("я люблю")[-1].strip().split(".")[0]
        memory.append(f"Користувач любить {hobby}.")
    elif "я з" in user_input.lower():
        city = user_input.split("я з")[-1].strip().split()[0]
        memory.append(f"Користувач з міста {city}.")
    return list(set(memory))[-5:]

# === Головна логіка чату ===
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_input = update.message.text.strip()

    # Завантаження даних користувача
    context_lines, memory_facts = await load_user_data(user_id)

    # Оновлення пам’яті
    memory_facts = update_memory(memory_facts, user_input)

    # Формування промпту
    prompt = BOT_PERSONALITY
    if memory_facts:
        prompt += "Факти про користувача:\n" + "\n".join(memory_facts) + "\n\n"
    prompt += "Діалог:\n" + "\n".join(context_lines[-10:]) + f"\nКористувач: {user_input}\nБот:"

    # Генерація відповіді
    input_ids = tokenizer.encode(prompt, return_tensors="pt", truncation=True, max_length=MAX_CONTEXT_TOKENS)
    output_ids = model.generate(
        input_ids,
        max_length=MAX_CONTEXT_TOKENS + 80,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,
        top_k=50,
        top_p=0.95,
        temperature=0.9,
        no_repeat_ngram_size=2
    )
    full_output = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    reply = full_output[len(prompt):].strip().split("\n")[0]

    # Оновлення контексту
    context_lines.append(f"Користувач: {user_input}")
    context_lines.append(f"Бот: {reply}")
    context_lines = context_lines[-20:]

    # Збереження
    await save_user_data(user_id, context_lines, memory_facts)

    # Відповідь користувачу
    await update.message.reply_text(reply)

# === Запуск бота ===
if __name__ == "__main__":
    asyncio.run(init_db())
    TELEGRAM_TOKEN = "7756341764:AAH65M7ZKAU2mWk-OFerfu5own6QMgkM574"  # Встав свій токен

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    print("Бот з базою даних запущено!")
    app.run_polling()
