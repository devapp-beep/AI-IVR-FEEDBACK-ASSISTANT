from flask import Blueprint, request, jsonify
from rich import print
from ..services.messaging_service import FeedbackHandler

twilio_webhook_bp = Blueprint("twilio_webhook", __name__)

@twilio_webhook_bp.post("/twilio/incoming")
def twilio_incoming():
    """Webhook endpoint for Twilio to forward incoming SMS data."""
    try:
        data = request.form.to_dict() or request.get_json(silent=True) or {}
        if not data:
            return jsonify({"error": "Payload needed"}), 400

        print(f"[bold cyan]📥 Twilio Webhook Data:[/bold cyan] {data}")

        result = FeedbackHandler.handle_twilio_incoming(data)
        return result
    except Exception as e:
        print(f"[bold red]Twilio Webhook Error:[/bold red] {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
