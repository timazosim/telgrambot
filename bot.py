from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Загружаем модель и токенизатор (например, DialoGPT или другую открытую модель)
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Функция для генерации ответа
def get_response(user_input, chat_history_ids=None):
    # Кодируем входной текст
    new_input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors="pt")
    
    # Объединяем историю чата с новым вводом
    if chat_history_ids is not None:
        bot_input_ids = torch.cat([chat_history_ids, new_input_ids], dim=-1)
    else:
        bot_input_ids = new_input_ids
    
    # Генерируем ответ
    chat_history_ids = model.generate(
        bot_input_ids,
        max_length=1000,
        pad_token_id=tokenizer.eos_token_id,
        no_repeat_ngram_size=3,
        do_sample=True,
        top_k=50,
        top_p=0.95,
        temperature=0.8
    )
    
    # Декодируем ответ
    response = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)
    return response, chat_history_ids

# Основной цикл чата
print("Чат-бот готов! Введите 'выход' для завершения.")
chat_history_ids = None

while True:
    user_input = input("Вы: ")
    if user_input.lower() == "выход":
        print("Чат-бот: Пока!")
        break
    
    response, chat_history_ids = get_response(user_input, chat_history_ids)
    print(f"Чат-бот: {response}")
