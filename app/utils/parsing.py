import json
import re
from typing import Any, Dict, List, Optional
from rich import print

# Keep placeholders consistent with your original
PLACEHOLDER_VALUES = {"user", "caller", "unknown", "null", ""}

def only_digits(s: Optional[str]) -> str:
    """Removes all non-digit characters from a string."""
    return re.sub(r"\D+", "", s or "")

def get_caller_number_from_body(body: Dict[str, Any]) -> Optional[str]:
    """
    Extracts the caller's E.164 phone number from the Vapi payload.
    Checks multiple common paths for robustness.
    """
    paths: List[List[str]] = [
        ["customer", "number"],
        ["message", "customer", "number"],
        ["call", "from", "phoneNumber"],
        ["message", "call", "from", "phoneNumber"],
        ["call", "caller_number"],
    ]
    for p in paths:
        node: Any = body
        for key in p:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                node = None
                break
        if node:
            return str(node)
    return None

def get_email_from_history(body: Dict[str, Any]) -> Optional[List[Optional[str]]]:
    """
    Extracts the user email and phone from the LATEST successful 'get_user_info'
    result in the conversation history, representing the current identity.
    Returns [latest_email, latest_phone] or None.
    """
    latest_email: Optional[str] = None
    latest_phone: Optional[str] = None
    try:
        artifact_messages = (body.get("message", {})
                                .get("artifact", {})
                                .get("messages", []))

        for msg in artifact_messages:
            if msg.get("role") == "tool_call_result" and msg.get("name") == "get_user_info":
                result_str = msg.get("result")
                # Only process non-error results
                if result_str and result_str != '{"error":"No matching record"}':
                    user_info = json.loads(result_str)
                    email = user_info.get("email")
                    phone = user_info.get("phone")
                    if email or phone:
                        latest_email = email
                        latest_phone = phone

        return [latest_email, latest_phone]
    except Exception as e:
        print(f"[bold red]Error extracting email/phone from history:[/bold red] {e}")
        return None
