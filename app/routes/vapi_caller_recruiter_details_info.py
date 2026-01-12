from flask import Blueprint, request, jsonify
from rich import print
from ..services.messaging_service import FeedbackHandler

vapi_caller_recruiter_details_info_bp = Blueprint("vapi_caller_recruiter_details_info", __name__)

@vapi_caller_recruiter_details_info_bp.post("/caller_recruiter_info")
def vapi_caller_recruiter_details_info():
    """
    Handles incoming Vapi tool call requests, executes functions via the service,
    and returns results in the expected shape.
    """
    print("function calledd vapi rcaller recruiter details info ")
    try:
        body = request.get_json(silent=True)
        if not body:
            return jsonify({"error": "No JSON body received"}), 400
        print("[bold magenta]Received Vapi payload[/bold magenta]")
        result, status_code = FeedbackHandler.get_caller_recruiter_info(body)
        # print the result
        print("[bold green]Status Code:[/bold green]", status_code)
        print("[bold green]Results:[/bold green]", result)
        return result, status_code
    except Exception as e:
        print(f"[bold red]Global Handler Error:[/bold red] {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500