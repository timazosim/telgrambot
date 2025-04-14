import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import re

# Загружаем модель и токенизатор
model_name = "mistralai/Mixtral-8x7B-Instruct-v0.1"  # Можно заменить на "microsoft/DialoGPT-medium" для простоты
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, device_map="auto")

# Инициализация истории чата
chat_history = []

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

def get_response(user_input, history, max_history_len=5):
    """Генерирует ответ на основе ввода и истории."""
    if not user_input.strip():
        return "Пожалуйста, введите сообщение.", history

    # Определяем, является ли ввод вопросом
    is_question = "?" in user_input or user_input.lower().startswith(("что", "как", "почему", "кто", "где", "когда"))

    # Форматируем текущий ввод
    formatted_input = format_input(user_input, is_question)

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
            max_new_tokens=200,  # Ограничиваем длину ответа
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

        return response, history

    except Exception as e:
        return f"Ошибка при генерации ответа: {str(e)}", history

# Основной цикл чата
print("Чат-бот готов! Введите 'выход' для завершения или 'очистить' для сброса истории.")
while True:
    user_input = input("Вы: ")
    if user_input.lower() == "выход":
        print("Чат-бот: До свидания!")
        break
    elif user_input.lower() == "очистить":
        chat_history = []
        print("Чат-бот: История очищена!")
        continue

    response, chat_history = get_response(user_input, chat_history)
    print(f"Чат-бот: {response}")
