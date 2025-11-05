import os
import time
import threading
import queue
import requests
import re
from flask import jsonify

class FeedbackHandler:
    sms_queue = queue.Queue()
    last_sms_sent = {}
    SMS_COOLDOWN_SECONDS = 100 
    TEXTLINE_TOKEN = os.getenv("TEXTLINE_API_KEY")  # Store safely in .env
    URL_EMAIL = os.getenv("URL_EMAIL")
    EMAIL_TO = os.getenv("EMAIL_TO")

    @staticmethod
    def paste_feedback_data(data):
        print("in paste_feedback_data", data)

        try:
            tool_call = data.get("message", {}).get("toolCalls", [])[0]
            args = tool_call["function"]["arguments"]
            call_number = call_number = (data.get("message", {}).get("customer", {}).get("number"))
            caller_name = args.get("Name")
            contact_number = args.get("contact_number")
            mood = args.get("Mood", "").strip().lower()
            objective = args.get("Objective")
            feedback = args.get("feedback_Summary") or args.get("feedback_summary")
            feedback_for = args.get("feedback_for")
            should_send_review_link = args.get("should_send_review_link", False)
            same_number = args.get("should_send_same_number", True)
            print( "[bold yellow] same_number", same_number)
            if same_number is True and call_number is not None:
                contact_number = call_number
            if contact_number is None or contact_number == "" or contact_number == "null" or contact_number == "None":
                contact_number = call_number

        except Exception as e: 
            print("❌ Error parsing data:", e)
            return jsonify({"status": "error", "message": "Invalid data format"}), 200


        try:
            summary_parts = []
            if objective:
                summary_parts.append(objective)
            if feedback:
                summary_parts.append(feedback)
            summary_text = ". ".join(summary_parts) if summary_parts else ""
            # Always send email, regardless of mood or link flag
            email_payload = {
                "email": FeedbackHandler.EMAIL_TO,
                "subject": f"{mood.title()} Feedback from {caller_name} for {feedback_for}",
                "body": f"{caller_name} called my feedback line from the number {contact_number} "
                        f"to leave a feedback for {feedback_for}.",
                "summary": summary_text,
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            email_response = requests.post(FeedbackHandler.URL_EMAIL, headers=headers, json=email_payload, timeout=10)
            if email_response.status_code in [200, 201]:
                print(f"📧 Email sent successfully for {caller_name}")
            else:
                print(f"❌ Failed to send email: {email_response.text}")
        except Exception as e:
            print(f"⚠️ Error sending email: {e}")
            return jsonify({"status": "error", "error": "Error sending email"}), 200
        # SMS validation
        if not contact_number:
            print("❌ Missing phone number")
            return jsonify({"status": "error", "error": "Missing phone number, ask for email"}), 200


        contact_number = str(contact_number).strip()
        if re.fullmatch(r"\d{10}", contact_number):
            contact_number = f"+1{contact_number}"
        elif not contact_number.startswith("+"):
            print(f"❌ Invalid phone number format: {contact_number}")
            return {"status": "error", "message": "Invalid number, ask for email"}
        if not re.fullmatch(r"\+[1-9]\d{7,14}$", contact_number):
            print(f"❌ Phone number not E.164 compliant: {contact_number}")
            return {"status": "error", "message": "Invalid number, ask for email"}


        # Send SMS only when mood is positive and should_send_review_link is True
        now = time.time()
        last_sent_time = FeedbackHandler.last_sms_sent.get(contact_number, 0)
        if now - last_sent_time < FeedbackHandler.SMS_COOLDOWN_SECONDS:
            print(f"ℹ️ SMS not sent (cooldown active for {contact_number})")
            return jsonify({"status": "success", "message": "SMS sent, but cooldown active"}), 200;

        if mood == "positive" and should_send_review_link:
            first_name = caller_name.split()[0].capitalize()
            sms_text = (
                f"Hi {first_name}, \n \nCynet Health would appreciate your feedback."
                f"You can highlight our employee’s name if you wish. Please click on the link below.\n"
                f"\nhttps://tinyurl.com/cynetreview \n \nThanks!!"
                
            )
            FeedbackHandler.sms_queue.put({
                "to": contact_number,
                "text": sms_text
            })
            FeedbackHandler.last_sms_sent[contact_number] = now
            print(f"📩 Queued Textline message to {contact_number}")
        else:
            print(f"ℹ️ SMS not sent (mood={mood}, should_send_review_link={should_send_review_link})")

        return jsonify({"status": "queued", "message": "Email sent, SMS queued if applicable"}), 200

    @staticmethod
    def process_sms_queue():
        """Background worker to send queued messages via Textline"""
        TEXTLINE_TOKEN = os.getenv("TEXTLINE_API_KEY")
        while True:
            task = FeedbackHandler.sms_queue.get()
            if not task:
                time.sleep(1)
                continue

            to_number = task["to"]
            text = task["text"]

            print(f"📨 Sending Textline message to {to_number}")

            url = "https://application.textline.com/api/conversations.json"
            headers = {
                "Content-Type": "application/json",
                "X-TGP-ACCESS-TOKEN": f"{TEXTLINE_TOKEN}"
            }
            payload = {
                "phone_number": to_number,
                "group_uuid": "",
                "comment": {"body": text},
                "resolve": "1"
            }

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                if response.status_code in [200, 201]:
                    print(f"✅ Message sent successfully to {to_number}")
                else:
                    print(f"❌ Failed to send to {to_number}: {response.text}")
            except Exception as e:
                print(f"⚠️ Error sending to {to_number}: {e}")

            FeedbackHandler.sms_queue.task_done()
            time.sleep(0.5)
