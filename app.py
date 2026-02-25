from dotenv import load_dotenv
load_dotenv()

from app import create_app
from flask_cors import CORS
import threading
from app.services.messaging_service import FeedbackHandler

app = create_app()
CORS(
    app,
    origins=["*"],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS"]
)
threading.Thread(target=FeedbackHandler.process_sms_queue, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
