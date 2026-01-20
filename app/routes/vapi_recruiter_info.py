from flask import Blueprint, request, jsonify
from rich import print
from ..services.messaging_service import FeedbackHandler

vapi_recruiter_info_bp = Blueprint("vapi_recruiter_info", __name__)

@vapi_recruiter_info_bp.post("/recruiter_info")
def vapi_recruiter_info():
    """
    Handles incoming Vapi tool call requests, executes functions via the service,
    and returns results in the expected shape.
    """
    try:
        body = request.get_json(silent=True)
        if not body:
            return jsonify({"error": "No JSON body received"}), 400
        if not FeedbackHandler.verify_vapi_request():
            return jsonify({"error": "Unauthorized"}), 401
        print("[bold magenta]Received Vapi payload[/bold magenta]")
        result, status_code = FeedbackHandler.get_recruiter_info(body)
        print("[bold green]Results:[/bold green]", result)
        return result, status_code
    except Exception as e:
        print(f"[bold red]Global Handler Error:[/bold red] {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500