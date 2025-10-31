from flask import Blueprint, request, jsonify
from rich import print
from ..services.messaging_service import FeedbackHandler

vapi_feedback_bp = Blueprint("vapi_feedback", __name__)

@vapi_feedback_bp.post("/user_feedback")
def vapi_tools():
    """
    Handles incoming Vapi tool call requests, executes functions via the service,
    and returns results in the expected shape.
    """
    try:
        # print("in vapi_feedback_controller", data.message.toolCalls[0].function.arguments)
        body = request.get_json(silent=True)
        if not body:
            return jsonify({"error": "No JSON body received"}), 400

        print("[bold magenta]Received Vapi payload[/bold magenta]")
        results = FeedbackHandler.paste_feedback_data(body)
        return jsonify({"results": results})
    except Exception as e:
        print(f"[bold red]Global Handler Error:[/bold red] {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
