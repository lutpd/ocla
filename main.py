import os
import asyncio
import logging
from flask import Flask, request, jsonify
from bot import init_qdrant, create_application, setup_webhook, process_update

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def health():
    return jsonify({
        "status": "running",
        "service": "Telegram AI Chatbot"
    })

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update_data = request.get_json()
        logger.info(f"Received webhook update")
        
        # Use asyncio to run the async function
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_update(update_data))
            loop.close()
            return jsonify({"status": "ok"})
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return jsonify({"status": "error"}), 400

def main():
    logger.info("Initializing bot...")
    
    # Initialize QDRANT
    init_qdrant()
    
    # Create Telegram application
    create_application()
    
    # Setup webhook asynchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook())
    loop.close()
    
    # Start Flask server
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
