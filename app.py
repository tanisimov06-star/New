import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import json
import os
import asyncio
from openai import OpenAI
import chromadb
from sentence_transformers import SentenceTransformer
import PyPDF2
import docx


embedder = SentenceTransformer('paraphrase-albert-small-v2')
chroma_client = chromadb.Client()
collection = chroma_client.create_collection(
    
    name ='documents',
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 100,
        "hnsw:M": 16  
    }
)


def text_from_pdf(file_path: str) -> str:
    text = ""
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.page:
            text += page.extract_text()
    return text

def text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])
def text_chunk(text: str, chunk_size: int=500) -> list:
    words = text.split()
    chunk = []
    for i in range(0, len(words), chunk_size):
        chunk.append(" ".join(words[i:i + chunk_size]))
    return chunk
def vector_db(chunk: list, doc_id: str):
    embeddings = embedder.encode(chunk).tolist()
    collection.add(
        embeddings=embeddings,
        documents=chunk,
        ids=[f"{doc_id}_{i}" for i in range(len(chunk))]
    )
def search(query: str, top_k:  int=3)->list:
    query_embedding = embedder.encode([query]).tolist()
    result = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k
    )
    return result["documents"][0] if result["documents"] else []

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


def search_with_openrouter(query: str) -> str:
    models_to_try = [
        "openrouter/free:online", 
    ]
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/MySmartAssistant228Bot",
        "X-Title": "Telegram AI Bot"
    }
    
    for model in models_to_try:
        try:
            
            if model.endswith(":online"):
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": query}],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            else:
                
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
                logging.info(f"✅ Поиск сработал с моделью: {model}")
                return result['choices'][0]['message']['content']
            else:
                logging.warning(f"Модель {model} вернула {response.status_code}: {response.text[:100]}")
        except Exception as e:
            logging.error(f"Ошибка с моделью {model}: {e}")
            continue
    
    return "❌ Ни одна модель поиска недоступна. Попробуйте позже."

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


async def head_document(update: Update, context):
    file = await update.message.document.get_file()
    file_path = f"temp_{update.message.document.file_name}"
    await file.download_to_drive(file_path)

    if update.message.document.file_name.endswith('.docx'):
        text = text_from_docx(file_path)
    elif update.message.document.file_name.endswith('.pdf'):
        text = text_from_pdf(file_path)
    else:
        await update.message.reply_text("Поддериживаем только файлы PDF и DOCX")
        return
    chunk = text_chunk(text)
    vector_db(chunk, str(update.effective_user.id))
    await update.message.reply_text(f"Документ обработан! Добавлено {len(chunk)} фрагментов")

async def ask_question(update: Update, context):
    query = update.message.text
    relevant_chunk = search(query)
    if not relevant_chunk:
        await update.message.reply_text("Не нашел ответ в зугруженных документах")
        return 
    context_text = "\n\n---\n\n".join(relevant_chunk)
    promt = f"""Ответь на вопрос, используя ТОЛЬКО информацию из документов ниже.
Документы:
{context_text}
Вопросы:
{query}
Ответ (со ссылкой на документ, если возможно):"""
    answer = get_api(update.effective_user.id, promt)
    await update.message.reply_text(answer)

async def head(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_message = update.message.text

    doc_triggers = ["найди в документе", "поищи в документе", "по документу", "согласно документу ", "в документе","исходя из документа",
    "где в документе"]
    if any(trigger in user_message.lower() for trigger in doc_triggers):
        await ask_question(update, context)
        return


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
    app.add_handler(MessageHandler(filters.Document.ALL, head_document))
    print("AI-бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()    