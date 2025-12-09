import os
import time
import threading
import queue
import requests
import re
from flask import jsonify
from google.cloud import bigquery

class FeedbackHandler:
    sms_queue = queue.Queue()
    last_sms_sent = {}
    SMS_COOLDOWN_SECONDS = 100 
    TEXTLINE_TOKEN = os.getenv("TEXTLINE_API_KEY")  # Store safely in .env
    URL_EMAIL = os.getenv("URL_EMAIL")
    EMAIL_TO = os.getenv("EMAIL_TO")
    project_id = os.getenv("GCLOUD_PROJECT")
    print("project_id", project_id)
    dataset_id = os.getenv("GCLOUD_DATASET_ID")
    table_id = os.getenv("GCLOUD_TABLE", "recruiters_nxs")
    VALID_DOMAINS = [
           "cynetsystems.com",
           "cynethealth.com",
           "cynetcorp.com",
           "cynetlocums.com",
    ]
    DOMAIN_FIXES = {
        "sainetsystems.com": "cynetsystems.com",
        "sianetsystems.com": "cynetsystems.com",
        "sainethealth.com": "cynethealth.com",
        "sianethealth.com": "cynethealth.com",
        "sainetcorp.com": "cynetcorp.com",
        "sianetcorp.com": "cynetcorp.com",
        "sainetlocums.com": "cynetlocums.com",
        "sianetlocums.com": "cynetlocums.com",

    }
    
    @staticmethod
    def create_bigquery_client():
        keyfile_path = "credentials.json"
        if not keyfile_path:
            raise ValueError("Service account key file not found. Set GCLOUD_KEYFILE.")
        return bigquery.Client.from_service_account_json(keyfile_path)

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
            if caller_name is None or caller_name == "" or caller_name == "null" or caller_name == "Caller":
                caller_name = "there"
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
                f"Hi {first_name}, \n \nCynet Health would appreciate your feedback. "
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

    def normalize_name(name):
        """Normalize spoken name from voice / chat"""
        if not name:
            return ""
        name = name.lower().strip()
        name = re.sub(r'[^a-z ]', '', name)      # remove symbols
        name = re.sub(r'\s+', ' ', name)         # normalize spaces
        return name
    
    def normalize_domain(email):
        if "@" not in email:
            return email
        local, domain = email.split("@", 1)
        domain = FeedbackHandler.DOMAIN_FIXES.get(domain, domain)
        domain = re.sub(r"(sai|sia|sei)[\-\s]?net", "cynet", domain)
        if domain not in FeedbackHandler.VALID_DOMAINS:
            raise ValueError("Invalid company domain")
        return f"{local}@{domain}"
   
    def get_recruiter_info(data):
        print("in get_recruiter_info", data)

        tool_call = data.get("message", {}).get("toolCalls", [])[0]
        args = tool_call["function"]["arguments"]
        toll_call_id = tool_call.get("id")
        print("toll_call_id", toll_call_id)

        # Accept inputs
        spoken_name = FeedbackHandler.normalize_name(args.get("recruiterName", ""))
        received_email = args.get("recruiterEmail", "").strip().lower()
        spoken_number = args.get("recruiterNumber", "")
        print("received_number", spoken_number)
        spoken_email = FeedbackHandler.normalize_domain(received_email)
        if not spoken_name and not spoken_email and not spoken_number:
            return jsonify({
                "status": "error",
                "message": "Recruiter name, email or number is required"
            }), 400
        print("before client creation")    

        client = FeedbackHandler.create_bigquery_client()
        print("after client creation", client)

        # --------------------------------
        # CASE 1: EMAIL ONLY (Exact match)
        # --------------------------------
        if spoken_email and not spoken_name and not spoken_number:

            query = f"""
                SELECT name, email, id, active
                FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`
                WHERE LOWER(email) = @email
                And active is True
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("email", "STRING", spoken_email)
                ]
            )
        # --------------------------------
        # CASE 2: NUMBER ONLY (Exact match)
        # --------------------------------
        elif spoken_number:
            query = f"""
                SELECT name, email, id, active
                FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`
                WHERE phone = @phone
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("phone", "STRING", spoken_number)
                ]
            )

        # --------------------------------
        # CASE 2: NAME ONLY (ADVANCED FUZZY - WORD-LEVEL MATCHING)
        # --------------------------------
        elif spoken_name and not spoken_email:

            query = f"""
                WITH name_parts AS (
                    SELECT
                        name,
                        email,
                        id,
                        active,
                        LOWER(name) AS name_lower,
                        SPLIT(LOWER(name), ' ') AS name_words,
                        @name AS spoken_name,
                        SPLIT(@name, ' ') AS spoken_words
                    FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`
                    WHERE active is True
                ),
                scored_names AS (
                    SELECT
                        name,
                        email,
                        id,
                        active,
                        name_lower,
                        spoken_name,
                        name_words,
                        spoken_words,
                        
                        -- Full string fuzzy match
                        EDIT_DISTANCE(name_lower, spoken_name) AS full_lev,
                        
                        -- First word match (first name) - exact distance
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 0 AND ARRAY_LENGTH(spoken_words) > 0 
                            THEN EDIT_DISTANCE(name_words[OFFSET(0)], spoken_words[OFFSET(0)])
                            ELSE 999
                        END AS first_word_lev,
                        
                        -- Second word match (last name) - exact distance if both have second words
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(spoken_words) > 1 
                            THEN EDIT_DISTANCE(name_words[OFFSET(1)], spoken_words[OFFSET(1)])
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(spoken_words) = 1 
                            THEN 0  -- Spoken has only first name, that's OK
                            ELSE 999
                        END AS second_word_lev,
                        
                        -- Check if first word matches (exact, fuzzy, or prefix)
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 0 AND ARRAY_LENGTH(spoken_words) > 0 
                            THEN name_words[OFFSET(0)] = spoken_words[OFFSET(0)] 
                                 OR EDIT_DISTANCE(name_words[OFFSET(0)], spoken_words[OFFSET(0)]) <= 3
                                 OR STARTS_WITH(name_words[OFFSET(0)], spoken_words[OFFSET(0)])
                                 OR STARTS_WITH(spoken_words[OFFSET(0)], name_words[OFFSET(0)])
                            ELSE FALSE
                        END AS first_word_match,
                        
                        -- Check if second word matches (when both have second words)
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(spoken_words) > 1 
                            THEN name_words[OFFSET(1)] = spoken_words[OFFSET(1)] 
                                 OR EDIT_DISTANCE(name_words[OFFSET(1)], spoken_words[OFFSET(1)]) <= 3
                                 OR STARTS_WITH(name_words[OFFSET(1)], spoken_words[OFFSET(1)])
                                 OR STARTS_WITH(spoken_words[OFFSET(1)], name_words[OFFSET(1)])
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(spoken_words) = 1 
                            THEN TRUE  -- Only first name spoken, that's acceptable
                            ELSE TRUE  -- No second word in either, consider it a match
                        END AS second_word_match,
                        
                        -- Check if spoken name is prefix of full name (shivani -> shivani sati)
                        STARTS_WITH(name_lower, spoken_name) AS prefix_match,
                        
                        -- Check if full name contains spoken name
                        name_lower LIKE CONCAT('%', spoken_name, '%') AS contains_match
                        
                    FROM name_parts
                )
                SELECT
                    name,
                    email,
                    id,
                    active,
                    full_lev,
                    first_word_lev,
                    second_word_lev,
                    first_word_match,
                    second_word_match,
                    prefix_match,
                    contains_match
                FROM scored_names
                WHERE
                    -- Match conditions (flexible matching):
                    -- 1. First word matches (exact, fuzzy within 3 chars, or prefix)
                    --    AND (second word matches OR prefix match OR full string close)
                    (
                        first_word_match = TRUE
                        AND (
                            second_word_match = TRUE
                            OR prefix_match = TRUE
                            OR full_lev <= 4
                        )
                    )
                    -- 2. OR full string is reasonably close (handles typos in first word)
                    OR full_lev <= 4
                    -- 3. OR prefix match (handles partial names)
                    OR prefix_match = TRUE
                ORDER BY
                    -- Priority: 
                    -- 1. Exact first word match
                    CASE WHEN first_word_lev = 0 THEN 1 ELSE 2 END,
                    -- 2. Prefix match (partial first name)
                    prefix_match DESC,
                    -- 3. Exact second word match
                    CASE WHEN second_word_lev = 0 THEN 1 ELSE 2 END,
                    -- 4. Then by fuzzy distances
                    first_word_lev ASC,
                    second_word_lev ASC,
                    full_lev ASC
                LIMIT 10
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("name", "STRING", spoken_name)
                ]
            )

        # --------------------------------
        # CASE 3: EMAIL + NAME (VERIFY BOTH)
        # --------------------------------
        else:

            query = f"""
                SELECT
                    name,
                    email,
                    id,
                    active,

                    EDIT_DISTANCE(LOWER(name), @name) AS lev,
                    STARTS_WITH(LOWER(name), @name) AS prefix_match

                FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`

                WHERE
                    LOWER(email) = @email
                    AND (
                        EDIT_DISTANCE(LOWER(name), @name) <= 3
                        OR STARTS_WITH(LOWER(name), @name)
                    )
                    And active is True

                ORDER BY
                    prefix_match DESC,
                    lev ASC
               
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("email", "STRING", spoken_email),
                    bigquery.ScalarQueryParameter("name", "STRING", spoken_name)
                ]
            )

        # --------------------------------
        # EXECUTE QUERY
        # --------------------------------
        print("before query execution")
        rows = list(client.query(query, job_config=job_config).result())
        print("after query execution")
        # --------------------------------
        # HANDLE NO RESULT
        # --------------------------------
        if not rows:
            vapi_response = {
                "results": [
                    {
                        "toolCallId": toll_call_id,
                        "result": {
                            "status": "not_found",
                            "message": "No recruiter found"
                        }
                    }
                ]
            }
            return jsonify(vapi_response), 404

        # --------------------------------
        # FORMAT RESPONSE
        # --------------------------------
        results = []
        for row in rows:
            results.append({
                "name": row.get("name"),
                "email": row.get("email"),
                "id": row.get("id"),
                "active_status": row.get("active"),
               
            })
        print("results are= ", results)

        # --------------------------------
        # MULTI MATCH CONFIRMATION
        # --------------------------------
        if len(results) > 1:
            vapi_response = {
                "results":[
                    {
                        "toolCallId": toll_call_id,
                        "result": {
                            "status": "confirm",
                            "message": "Multiple recruiters found. Please confirm:",
                            "candidates": results[:5]
                        }
                    }
                ]
            }
            return jsonify(vapi_response), 200

        # --------------------------------
        # SINGLE MATCH SUCCESS
        # --------------------------------
        vapi_response = {
            "results": [
                {
                    "toolCallId": toll_call_id,
                    "result": {
                        "status": "success",
                        "message": "Recruiter identified successfully",
                        "data": results[0]
                    }
                }
            ]
        }
        return jsonify(vapi_response), 200

