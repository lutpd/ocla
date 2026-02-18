# Telegram AI Chatbot with QDRANT

A Telegram chatbot powered by OpenCode AI with web search, URL fetching, and QDRANT vector storage.

## Features

- AI-powered conversations using OpenCode API
- Web search capability (DuckDuckGo)
- URL fetching and content summarization
- Persistent memory using QDRANT vector database
- Session management with `/bbb` command
- Free deployment on Render.com

## Setup

### 1. Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the **BOT TOKEN**

### 2. Get QDRANT Credentials (Free)

1. Go to https://cloud.qdrant.io
2. Create a free account
3. Create a new cluster
4. Copy the **URL** and **API Key**

### 3. Deploy on Render.com

#### Option A: Using render.yaml (Blueprint)

1. Push this code to a GitHub repository
2. Go to https://dashboard.render.com
3. Click "New" → "Blueprint"
4. Connect your GitHub repository
5. Set environment variables:
   - `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
   - `QDRANT_URL` - Your QDRANT cluster URL
   - `QDRANT_API_KEY` - Your QDRANT API key
6. Click "Apply"

#### Option B: Manual Setup

1. Go to https://dashboard.render.com
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Set:
   - **Name**: telegram-ai-chatbot
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
5. Add environment variables:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENAI_API_KEY=sk-7ZoyUuEjlVeDrcCbIwdE3yJXy9U840McF7HL5FZtIPKxp9s3vwaDCW3QjXteOPQG
   OPENAI_BASE_URL=https://opencode.ai/zen/v1/
   MODEL_ID=minimax-m2.5-free
   QDRANT_URL=your_qdrant_url
   QDRANT_API_KEY=your_qdrant_api_key
   ```
6. Click "Create Web Service"

### 4. Local Development

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your values

# Run the bot
python bot.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/bbb` | Create new chat session |
| `/help` | Show help message |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `OPENAI_API_KEY` | Yes | OpenCode API key |
| `OPENAI_BASE_URL` | Yes | OpenCode API base URL |
| `MODEL_ID` | Yes | Model ID to use |
| `QDRANT_URL` | No | QDRANT cluster URL (optional, enables persistent memory) |
| `QDRANT_API_KEY` | No | QDRANT API key (required if QDRANT_URL is set) |

## Architecture

```
Telegram User → Telegram API → Bot (Render.com)
                                ↓
                          OpenCode AI API
                                ↓
                          QDRANT (Vector DB)
```

## Notes

- Render free tier has 750 hours/month
- Bot may sleep after 15 minutes of inactivity (free tier)
- QDRANT free tier includes 1GB storage
- Without QDRANT, bot uses in-memory storage (resets on restart)
