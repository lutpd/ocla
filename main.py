import os
import subprocess
import threading
from app import app

def run_telegram_bot():
    subprocess.run(["python", "bot.py"])

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
