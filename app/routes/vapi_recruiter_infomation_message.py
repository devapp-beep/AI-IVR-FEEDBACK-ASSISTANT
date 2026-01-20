from flask import Blueprint, request, jsonify
from rich import print
from ..services.messaging_service import FeedbackHandler

vapi_recruiter_infomation_message = Blueprint("vapi_recruiter_infomation_message", __name__)

@vapi_recruiter_infomation_message.post("/send-recruiter-info-message")
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
        if not FeedbackHandler.verify_vapi_request():
            return jsonify({"error": "Unauthorized"}), 401
        result, status_code = FeedbackHandler.send_message_to_Caller(body)
        # print the result
        print("[bold green]Status Code:[/bold green]", status_code)
        print("[bold green]Results:[/bold green]", result)
        return result, status_code
    except Exception as e:
        print(f"[bold red]Global Handler Error:[/bold red] {e}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500