import os
import uuid
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import httpx

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-7ZoyUuEjlVeDrcCbIwdE3yJXy9U840McF7HL5FZtIPKxp9s3vwaDCW3QjXteOPQG")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://opencode.ai/zen/v1/")
MODEL_ID = os.getenv("MODEL_ID", "minimax-m2.5-free")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

COLLECTION_NAME = "telegram_chatbot"

openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL
)

qdrant_client: Optional[QdrantClient] = None

def init_qdrant():
    global qdrant_client
    if QDRANT_URL and QDRANT_API_KEY:
        try:
            qdrant_client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY
            )
            collections = qdrant_client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if COLLECTION_NAME not in collection_names:
                qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
                )
                logger.info(f"Created QDRANT collection: {COLLECTION_NAME}")
            else:
                logger.info(f"QDRANT collection already exists: {COLLECTION_NAME}")
        except Exception as e:
            logger.error(f"Failed to initialize QDRANT: {e}")
            qdrant_client = None
    else:
        logger.warning("QDRANT credentials not provided, using in-memory storage")

user_sessions: Dict[int, Dict[str, Any]] = {}

def get_or_create_session(user_id: int) -> Dict[str, Any]:
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "session_id": str(uuid.uuid4()),
            "messages": [],
            "created_at": datetime.now().isoformat()
        }
    return user_sessions[user_id]

def new_session(user_id: int) -> str:
    session_id = str(uuid.uuid4())
    user_sessions[user_id] = {
        "session_id": session_id,
        "messages": [],
        "created_at": datetime.now().isoformat()
    }
    return session_id

async def web_search(query: str) -> str:
    try:
        search_url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1"
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, timeout=10)
            data = response.json()
            
        results = []
        if data.get("AbstractText"):
            results.append(f"Summary: {data['AbstractText']}")
        if data.get("AbstractURL"):
            results.append(f"Source: {data['AbstractURL']}")
        
        related = data.get("RelatedTopics", [])[:3]
        for topic in related:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text']}")
        
        if results:
            return "\n".join(results)
        return "No search results found."
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Search error: {str(e)}"

async def fetch_url(url: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15, follow_redirects=True)
            text = response.text[:5000]
            return f"Content from {url}:\n\n{text}"
    except Exception as e:
        logger.error(f"URL fetch error: {e}")
        return f"Failed to fetch URL: {str(e)}"

async def save_to_qdrant(user_id: int, message: str, response: str, session_id: str):
    if not qdrant_client:
        return
    
    try:
        text_to_embed = f"User: {message}\nAssistant: {response}"
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text_to_embed
        )
        embedding = embedding_response.data[0].embedding
        
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "user_id": user_id,
                "session_id": session_id,
                "message": message,
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point]
        )
        logger.info(f"Saved conversation to QDRANT for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to save to QDRANT: {e}")

async def get_relevant_context(user_id: int, query: str) -> List[Dict]:
    if not qdrant_client:
        return []
    
    try:
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=query
        )
        embedding = embedding_response.data[0].embedding
        
        results = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=embedding,
            query_filter={
                "must": [
                    {"key": "user_id", "match": {"value": user_id}}
                ]
            },
            limit=3
        )
        
        return [{"message": r.payload["message"], "response": r.payload["response"]} for r in results]
    except Exception as e:
        logger.error(f"Failed to get context from QDRANT: {e}")
        return []

async def chat_with_ai(user_id: int, message: str) -> str:
    session = get_or_create_session(user_id)
    
    system_prompt = """You are a helpful AI assistant with access to web search and URL fetching capabilities.

When the user asks you to search the web, respond with: [SEARCH: query]
When the user asks you to fetch a URL, respond with: [FETCH: url]

You can also search automatically when you need current information.

Be helpful, concise, and accurate."""

    relevant_context = await get_relevant_context(user_id, message)
    context_text = ""
    if relevant_context:
        context_text = "\n\nRelevant past conversations:\n"
        for ctx in relevant_context:
            context_text += f"User: {ctx['message']}\nAssistant: {ctx['response']}\n"
    
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt + context_text}
    ]
    messages.extend(session["messages"][-10:])
    messages.append({"role": "user", "content": message})
    
    try:
        response = openai_client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            max_tokens=2048,
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message.content or ""
        
        if "[SEARCH:" in assistant_message:
            search_match = re.search(r'\[SEARCH:\s*([^\]]+)\]', assistant_message)
            if search_match:
                search_query = search_match.group(1).strip()
                search_results = await web_search(search_query)
                messages.append({"role": "assistant", "content": assistant_message})
                messages.append({"role": "user", "content": f"Search results for '{search_query}':\n{search_results}\n\nPlease provide a helpful response based on these results."})
                
                response = openai_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.7
                )
                assistant_message = response.choices[0].message.content or ""
        
        if "[FETCH:" in assistant_message:
            fetch_match = re.search(r'\[FETCH:\s*([^\]]+)\]', assistant_message)
            if fetch_match:
                url = fetch_match.group(1).strip()
                fetch_content = await fetch_url(url)
                messages.append({"role": "assistant", "content": assistant_message})
                messages.append({"role": "user", "content": f"Content fetched from {url}:\n{fetch_content}\n\nPlease summarize or answer based on this content."})
                
                response = openai_client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.7
                )
                assistant_message = response.choices[0].message.content or ""
        
        session["messages"].append({"role": "user", "content": message})
        session["messages"].append({"role": "assistant", "content": assistant_message})
        
        await save_to_qdrant(user_id, message, assistant_message, session["session_id"])
        
        return assistant_message
        
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return f"Error communicating with AI: {str(e)}"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return
    
    user_id = user.id
    new_session(user_id)
    
    await update.message.reply_text(
        "Welcome to AI Chatbot!\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/bbb - Start a new chat session\n"
        "/help - Show help message\n\n"
        "I can search the web and fetch URLs for you!"
    )

async def new_session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return
    
    user_id = user.id
    session_id = new_session(user_id)
    
    await update.message.reply_text(
        f"New chat session created!\nSession ID: {session_id[:8]}...\n\n"
        "Your previous conversation context has been cleared."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    await update.message.reply_text(
        "AI Chatbot Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/bbb - Start a new chat session\n"
        "/help - Show this help message\n\n"
        "Features:\n"
        "- AI-powered conversations\n"
        "- Web search capability\n"
        "- URL fetching and summarization\n"
        "- Persistent memory using QDRANT\n"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return
    
    user_id = user.id
    message_text = update.message.text
    
    await update.message.chat.send_action("typing")
    
    response = await chat_with_ai(user_id, message_text)
    
    if len(response) > 4096:
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i+4096])
    else:
        await update.message.reply_text(response)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not provided!")
        return
    
    init_qdrant()
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("bbb", new_session_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
