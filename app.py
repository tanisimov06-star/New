import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import json
import os
import asyncio
from openai import OpenAI



def save_history(messages):
    with open("history_bot.json", "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def load_history():
    try:
        with open("history_bot.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
        

memory = load_history()  

sys_memory = {
    "role": "system",
    "content": "Ты полезный помощник, отвечай коротко и по делу"
}

logging.basicConfig(format= '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


# DEEPSEEK_KEY_API = os.getenv("DEEPSEEK_KEY_API")
# if DEEPSEEK_KEY_API:
#     deepseek_client = OpenAI (
#         api_key=DEEPSEEK_KEY_API,
#         base_url= "https://api.deepseek.com"
#     )
#     DEEPSEEK_AVAILABLE = True
# else:
#     deepseek_client = None
#     DEEPSEEK_AVAILABLE = False
#     print("Ключ API не задан!")


# def search_deepseek(query: str) -> str:
    
    
#     if not DEEPSEEK_AVAILABLE:
#         return "❌ Поиск недоступен: API-ключ не задан"
    
#     try:
#         response = deepseek_client.chat.completions.create(
#             model="deepseek-chat",
#             messages = [{"role": "user", "content": query}],
#             temperature = 0.7,
#             max_tokens = 500,
#             tools = [{"type": "web_search"}]
#             )
        
        
#         answer = response.choices[0].message.content
        
        
#         if response.choices[0].message.tool_calls:
#             answer += "\n\n📚 **Источники:**"
#             for tool in response.choices[0].message.tool_calls:
#                 if tool.type == "web_search" and hasattr(tool, 'web_search'):
#                     url = tool.web_search.url if hasattr(tool.web_search, 'url') else str(tool.web_search)
#                     answer += f"\n• {url}"
        
#         return answer
        
#     except Exception as e:
#         return f"❌ Ошибка поиска: {e}"

def search_with_openrouter(query: str) -> str:

    model_to_try= [
         "qwen/qwen3.6-plus-preview:free",        
    "meta-llama/llama-4-maverick:free",      
    "zhipuai/glm-4-flash-250207:free",      
    "nvidia/nemotron-3-super-120b-a12b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-4-scout:free",         
    "google/gemini-2.5-flash-preview-04-17:free", 
    "google/gemini-2.5-pro-exp-03-25:free",  
    "google/gemini-2.0-flash-1b:free"        
]

    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    for model in model_to_try:
        try:
            data = {
            "model": model,
            "messages": [{"role": "user", "content": query}],
            "tools": [{"type": "web_search"}],
            "temperature": 0.7,
            "max_tokens": 500
        }
            response = requests.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
        except:
            continue
    return "Ни одна модель недоступна на данный момент времени"

BOT_TOKEN = os.getenv("BOT_TOKEN")
api_key = os.getenv("OPENROUTER_API_KEY")

model="openrouter/free"


def user_memory(user_id) -> list:
    user_id_str = str(user_id)
    if user_id_str not in memory:
        memory[user_id_str] = [sys_memory.copy()]
        save_history(memory)
    return memory[user_id_str]
    
def get_api(user_id: int, promt: str) -> str:

    user_id_str = str(user_id)




    base_url="https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        
    }

    history = user_memory(user_id)
    history.append({"role": "user", "content": promt})
    save_history(memory)

    data = {
        "model": model,
        "messages": history,
        "temperature": 0.7,
        "max_tokens": 500
        
    }
    try:
        response = requests.post(base_url, headers=headers, json=data, timeout=30)
        
        response.raise_for_status()
        result = response.json()
        ai = result['choices'][0]['message']['content'].strip()
        
        history.append({"role": "assistant", "content": ai})
        save_history(memory)

        if len(history) > 20:
            memory[user_id_str] = [history[0]] + history[-19:]
            save_history(memory)
        return ai    
    
    except requests.exceptions.RequestException as e:
        logging.error(f"OpenRouter API error: {e}")
        history.pop()
        save_history(memory)
        return "❌ Ошибка при обращении к AI. Попробуйте позже."

async def search_com(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 Введите поисковый запрос после команды.\n"
        "Например: `/search последние новости ИИ`",
        parse_mode="Markdown"
    )

async def headle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    if user_message.startswith("/search"):
        query = user_message[7:].strip()
    else:
        query = user_message.strip()
    if not query:
        await update.message.reply_text("Введите поисковой запрос")
        return
    await update.message.chat.send_action(action="typing")
    result = search_with_openrouter(query)
    await update.message.reply_text(result, parse_mode="Markdown")



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    await update.message.reply_text("🤖 Привет! Я AI-бот, подключенный к OpenRouter.\n\n"
        "Задай мне любой вопрос, и я постараюсь на него ответить.\n\n"
        "Команды:\n"
        "/start - показать это сообщение\n"
        "/help - помощь\n"
        "/clear - очистить историю диалога")

async def help_comm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Как пользоваться:\n\n"
        "Просто напиши мне любое сообщение, и я отвечу.\n"
        "Я использую нейросеть для генерации ответов.\n\n"
        "Команды:\n"
        "/clear - очистить историю диалога (если добавлю память)\n"
        "/start - главное меню"
    )
async def clear_comm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    user_id_str = str(user_id)

    memory[user_id_str] = [sys_memory.copy()]
    save_history(memory)

    await update.message.reply_text(
        "🧹 История диалога очищена!\n"
        "Теперь мы начинаем разговор с чистого листа."
    )




async def head(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_message = update.message.text

    search_triggers = ["найди", "поищи", "кто такой", "найти", "поиск", "узнай", "кто",]
    is_search = any (trigger in user_message.lower() for trigger in search_triggers)
    if is_search or user_message.startswith("/search"):
        await headle_search(update, context)
        return

    if not user_message.strip():
        await update.message.reply_text("Пожалуйста введите текст")
        return
    await update.message.chat.send_action(action="typing")
    ai_answer = get_api(user_id, user_message)      
    await update.message.reply_text(ai_answer)
    


def main():
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("search", search_com))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_comm ))
    app.add_handler(CommandHandler("clear", clear_comm))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, head))
    print("AI-бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()    