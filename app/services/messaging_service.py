import os
import time
import threading
import queue
import requests
import re
from flask import jsonify,request
from google.cloud import bigquery

class FeedbackHandler:
    sms_queue = queue.Queue()
    last_sms_sent = {}
    SMS_COOLDOWN_SECONDS = 100 
    TEXTLINE_TOKEN = os.getenv("TEXTLINE_API_KEY")  # Store safely in .env
    URL_EMAIL = os.getenv("URL_EMAIL")
    EMAIL_TO = os.getenv("EMAIL_TO")
    project_id = os.getenv("GCLOUD_PROJECT")
    call_data_project = os.getenv("GCLOUD_PROJECT_CALL_DATA")
    call_data_table = os.getenv("GCLOUD_TABLE_CALL_DATA")
    VAPI_SECRET = os.getenv("VAPI_SECRET")
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

    def get_immediate_manager_email(recruiter_email):
        client = FeedbackHandler.create_bigquery_client()

        query = """
            SELECT
                m.email AS immediate_manager_email
            FROM `cynetdatabase.Department_Data.Ph and India` e
            JOIN `cynetdatabase.Department_Data.Ph and India` m
                ON LOWER(e.immediate_manager) = LOWER(m.goes_by_name)
            WHERE LOWER(e.email) = LOWER(@email)
            LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("email", "STRING", recruiter_email)
            ]
        )

        try:
            rows = client.query(query, job_config=job_config).result()
            for row in rows:
                return row.immediate_manager_email
        except Exception as e:
            print(f"⚠️ Error querying immediate manager email: {e}")
        return None

    def verify_vapi_request():
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"{FeedbackHandler.VAPI_SECRET}":
            print("Unauthorized access attempt detected.")
            return False
        return True


    @staticmethod
    def paste_feedback_data(data):

        try:
            tool_call = data.get("message", {}).get("toolCalls", [])[0]
            args = tool_call["function"]["arguments"]
            call_number = call_number = (data.get("message", {}).get("customer", {}).get("number"))
            caller_name = args.get("Name")
            contact_number = args.get("contact_number")
            mood = args.get("Mood", "").strip().lower()
            objective = args.get("Objective")
            recruiter_name = args.get("recruiter_name")
            recruiter_email = args.get("recruiter_email")
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
            # of recruiter email incluse domain cynetcorp than i want the EMAIL_TO value to be myfeedback@cyentcorp.com if the domain is cynetlocums than i want the EMAIL_TO value to be myfeedback@cynetlocums.com if the domain is cynethealth than i want the EMAIL_TO value to be myfeedback@cynethealth.com and if cynetsystems than i want the EMAIL_TO value to be myfeedback@cynetsystems.com
            if recruiter_email:
                domain = recruiter_email.split("@")[-1]
                if domain == "cynetcorp.com":
                    EMAIL_TO_REC = "myfeedback@cynetcorp.com"
                    CC_SENIOR = os.getenv("CC_SENIOR_CORP")
                    REVIEW_LINK= "https://tinyurl.com/cynetreview"
                    CC_MANAGER = FeedbackHandler.get_immediate_manager_email(recruiter_email)
                elif domain == "cynetlocums.com":
                    EMAIL_TO_REC = "myfeedback@cynetlocums.com"
                    CC_MANAGER = FeedbackHandler.get_immediate_manager_email(recruiter_email)
                    CC_SENIOR = os.getenv("CC_SENIOR_LOCUMS")
                    REVIEW_LINK= "https://app.gatherup.com/f-164844"
                elif domain == "cynethealth.com":
                    EMAIL_TO_REC = "myfeedback@cynethealth.com"
                    CC_MANAGER = FeedbackHandler.get_immediate_manager_email(recruiter_email)
                    CC_SENIOR = os.getenv("CC_SENIOR_HEALTH")
                    REVIEW_LINK= "https://app.gatherup.com/f-132065"
                elif domain == "cynetsystems.com":
                    EMAIL_TO_REC = "myfeedback@cynetsystems.com"
                    CC_MANAGER = FeedbackHandler.get_immediate_manager_email(recruiter_email)
                    CC_SENIOR = os.getenv("CC_SENIOR_SYSTEMS")
                    REVIEW_LINK= "https://app.gatherup.com/f-164843"
                elif domain == "cynethealth.ca":
                    EMAIL_TO_REC = "myfeedback@cynethealth.ca"
                    CC_MANAGER = FeedbackHandler.get_immediate_manager_email(recruiter_email)
                    # CC_SENIOR = os.getenv("CC_SENIOR_HEALTH_CA")
                    REVIEW_LINK= "https://g.page/r/CYh2_NAwTxTrEBM/review"
            else:
                recruiter_email = FeedbackHandler.EMAIL_TO
                EMAIL_TO_REC = FeedbackHandler.EMAIL_TO
                CC_MANAGER = ""
                CC_SENIOR = ""
                REVIEW_LINK= "https://tinyurl.com/cynetreview"

            if mood == "positive" or mood == "neutral":
                # Build a proper CC list (exclude empty values)
                cc_list = []
                if CC_MANAGER:
                    cc_list.append(CC_MANAGER)
                if EMAIL_TO_REC and EMAIL_TO_REC != recruiter_email:
                    cc_list.append(EMAIL_TO_REC)

                email_payload = {
                    #  use the above conditional mail here to send the mail
                    "email": recruiter_email,
                    "cc_emails": cc_list,
                    "subject": f"INTERNAL TOOL TESTING, PLEASE IGNORE {mood.title()} Feedback from {caller_name} for {feedback_for}",
                    "body": f"{caller_name} called my feedback line from the number {contact_number} "
                            f"to leave a feedback for {feedback_for}.",
                    "summary": summary_text,
                }
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                email_response = requests.post(FeedbackHandler.URL_EMAIL, headers=headers, json=email_payload, timeout=10)
            if mood == "negative":
                cc_list =[]
                if CC_MANAGER:
                    cc_list.append(CC_MANAGER)
                if CC_SENIOR:
                    cc_list.append(CC_SENIOR)
                email_payload = {
                    "email": EMAIL_TO_REC,
                    "cc_emails": cc_list,
                    "subject": f"INTERNAL TOOL TESTING, PLEASE IGNORE {mood.title()} Feedback from {caller_name} for {feedback_for}",
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
                f"\n {REVIEW_LINK}\n \nThanks!!"
                
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
    
    def normalize_phone_number(phone):
        """
        Normalize phone number to match database format (+1XXXXXXXXXX).
        Handles:
        - 10 digits: "5713996469" -> "+15713996469"
        - 11 digits starting with 1: "15713996469" -> "+15713996469"
        - Already has +: "+15713996469" -> "+15713996469" (unchanged)
        """
        if not phone:
            return phone
        
        phone = str(phone).strip()
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', str(phone).strip())
        
        # If it already starts with +, return as is
        if cleaned.startswith('+'):
            return cleaned
        
        # Extract only digits
        digits_only = re.sub(r'\D', '', cleaned)
        
        # If 10 digits, add +1 prefix
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        
        # If 11 digits and starts with 1, add + prefix
        if len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        
        # For any other format, return as is (shouldn't happen in normal cases)
        return phone
   
    def get_recruiter_info(data):

        tool_call = data.get("message", {}).get("toolCalls", [])[0]
        args = tool_call["function"]["arguments"]
        toll_call_id = tool_call.get("id")


        # Accept inputs
        spoken_name = FeedbackHandler.normalize_name(args.get("recruiterName", ""))
        received_email = args.get("recruiterEmail", "").strip().lower()
        spoken_number = args.get("recruiterNumber", "")
        print("received_number", spoken_number)
        # Normalize phone number to match database format
        if spoken_number:
            normalized_number = FeedbackHandler.normalize_phone_number(spoken_number)
            print("normalized_number", normalized_number)
        else:
            normalized_number = None
        spoken_email = FeedbackHandler.normalize_domain(received_email)
        if not spoken_name and not spoken_email and not spoken_number:
            return jsonify({
                "status": "error",
                "message": "Recruiter name, email or number is required"
            }), 400
  

        client = FeedbackHandler.create_bigquery_client()


        # --------------------------------
        # CASE 1: EMAIL ONLY (Exact match)
        # --------------------------------
        if spoken_email and not spoken_name and not spoken_number:

            query = f"""
                SELECT NAME, PRIMARY_EMAIL, STATUS, PHONE_NO
                FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`
                WHERE LOWER(PRIMARY_EMAIL) = lower(@PRIMARY_EMAIL)
                
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("PRIMARY_EMAIL", "STRING", spoken_email)
                ]
            )
        # --------------------------------
        # CASE 2: NUMBER ONLY (Exact match)
        # --------------------------------
        elif spoken_number and normalized_number:
            query = f"""
                SELECT NAME, PRIMARY_EMAIL, STATUS, PHONE_NO
                FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`
                WHERE PHONE_NO LIKE CONCAT('%', @PHONE_NO, '%')
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("PHONE_NO", "STRING", normalized_number)
                ]
            )

        # --------------------------------
        # CASE 2: NAME ONLY (ADVANCED FUZZY - WORD-LEVEL MATCHING)
        # --------------------------------
        elif spoken_name and not spoken_email:

            query = f"""
                WITH name_parts AS (
                    SELECT
                        NAME,
                        PRIMARY_EMAIL,
                        PHONE_NO,
                        STATUS,
                        LOWER(NAME) AS name_lower,
                        SPLIT(LOWER(NAME), ' ') AS name_words,
                        @name AS spoken_name,
                        SPLIT(@name, ' ') AS spoken_words
                    FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`
                    WHERE STATUS = 'active'
                ),
                scored_names AS (
                    SELECT
                        NAME,
                        PRIMARY_EMAIL,
                        PHONE_NO,
                        STATUS,
                        name_lower,
                        @name AS SPOKEN_NAME,
                        SPLIT(@name, ' ') AS SPOKEN_WORDS,
                        
                        -- Full string fuzzy match
                        EDIT_DISTANCE(LOWER(NAME), LOWER(@name)) AS full_lev,
                        
                        -- First word match (first name) - exact distance
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 0 AND ARRAY_LENGTH(spoken_words) > 0 
                            THEN EDIT_DISTANCE(name_words[OFFSET(0)], SPOKEN_WORDS[OFFSET(0)])
                            ELSE 999
                        END AS first_word_lev,
                        
                        -- Second word match (last name) - exact distance if both have second words
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(SPOKEN_WORDS) > 1 
                            THEN EDIT_DISTANCE(name_words[OFFSET(1)], SPOKEN_WORDS[OFFSET(1)])
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(SPOKEN_WORDS) = 1 
                            THEN 0  -- Spoken has only first name, that's OK
                            ELSE 999
                        END AS SECOND_WORD_LEV,
                        
                        -- Check if first word matches (exact, fuzzy, or prefix)
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 0 AND ARRAY_LENGTH(SPOKEN_WORDS) > 0 
                            THEN name_words[OFFSET(0)] = SPOKEN_WORDS[OFFSET(0)] 
                                 OR EDIT_DISTANCE(name_words[OFFSET(0)], SPOKEN_WORDS[OFFSET(0)]) <= 3
                                 OR STARTS_WITH(name_words[OFFSET(0)], SPOKEN_WORDS[OFFSET(0)])
                                 OR STARTS_WITH(SPOKEN_WORDS[OFFSET(0)], name_words[OFFSET(0)])
                            ELSE FALSE
                        END AS FIRST_WORD_MATCH,
                        
                        -- Check if second word matches (when both have second words)
                        CASE 
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(SPOKEN_WORDS) > 1 
                            THEN name_words[OFFSET(1)] = SPOKEN_WORDS[OFFSET(1)] 
                                 OR EDIT_DISTANCE(name_words[OFFSET(1)], SPOKEN_WORDS[OFFSET(1)]) <= 3
                                 OR STARTS_WITH(name_words[OFFSET(1)], SPOKEN_WORDS[OFFSET(1)])
                                 OR STARTS_WITH(SPOKEN_WORDS[OFFSET(1)], name_words[OFFSET(1)])
                            WHEN ARRAY_LENGTH(name_words) > 1 AND ARRAY_LENGTH(SPOKEN_WORDS) = 1 
                            THEN TRUE  -- Only first name spoken, that's acceptable
                            ELSE TRUE  -- No second word in either, consider it a match
                        END AS SECOND_WORD_MATCH,
                        
                        -- Check if spoken name is prefix of full name (shivani -> shivani sati)
                        STARTS_WITH(name_lower, SPOKEN_NAME) AS prefix_match,
                        
                        -- Check if full name contains spoken name
                        name_lower LIKE CONCAT('%', SPOKEN_NAME, '%') AS contains_match
                        
                    FROM name_parts
                )
                SELECT
                    NAME,
                    PRIMARY_EMAIL,
                    PHONE_NO,
                    STATUS,
                    FULL_LEV,
                    FIRST_WORD_LEV,
                    SECOND_WORD_LEV,
                    FIRST_WORD_MATCH,
                    SECOND_WORD_MATCH,
                    PREFIX_MATCH,
                    CONTAINS_MATCH
                FROM scored_names
                WHERE
                    -- Match conditions (flexible matching):
                    -- 1. First word matches (exact, fuzzy within 3 chars, or prefix)
                    --    AND (second word matches OR prefix match OR full string close)
                    (
                        FIRST_WORD_MATCH = TRUE
                        AND (
                            SECOND_WORD_MATCH = TRUE
                            OR PREFIX_MATCH = TRUE
                            OR FULL_LEV <= 4
                        )
                    )
                    -- 2. OR full string is reasonably close (handles typos in first word)
                    OR FULL_LEV <= 4
                    -- 3. OR prefix match (handles partial names)
                    OR PREFIX_MATCH = TRUE
                ORDER BY
                    -- Priority: 
                    -- 1. Exact first word match
                    CASE WHEN FIRST_WORD_LEV = 0 THEN 1 ELSE 2 END,
                    -- 2. Prefix match (partial first name)
                    PREFIX_MATCH DESC,
                    -- 3. Exact second word match
                    CASE WHEN SECOND_WORD_LEV = 0 THEN 1 ELSE 2 END,
                    -- 4. Then by fuzzy distances
                    FIRST_WORD_LEV ASC,
                    SECOND_WORD_LEV ASC,
                    FULL_LEV ASC
                LIMIT 10
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("NAME", "STRING", spoken_name)
                ]
            )
        # --------------------------------
        # CASE 3: EMAIL + NAME (VERIFY BOTH)
        # --------------------------------
        else:

            query = f"""
                SELECT
                    NAME,
                    PRIMARY_EMAIL,
                    PHONE_NO,
                    STATUS,

                    EDIT_DISTANCE(LOWER(NAME), LOWER(@NAME)) AS lev,
                    STARTS_WITH(LOWER(NAME), LOWER(@NAME)) AS prefix_match

                FROM `{FeedbackHandler.project_id}.{FeedbackHandler.dataset_id}.{FeedbackHandler.table_id}`

                WHERE
                    LOWER(PRIMARY_EMAIL) = @PRIMARY_EMAIL
                    AND (
                        EDIT_DISTANCE(LOWER(NAME), LOWER(@NAME)) <= 3
                        OR STARTS_WITH(LOWER(NAME), LOWER(@NAME))
                    )
                    AND STATUS = 'active'

                ORDER BY
                    PREFIX_MATCH DESC,
                    LEV ASC
               
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("PRIMARY_EMAIL", "STRING", spoken_email),
                    bigquery.ScalarQueryParameter("NAME", "STRING", spoken_name),
                    bigquery.ScalarQueryParameter("PHONE_NO", "STRING", spoken_number)
                ]
            )

        # --------------------------------
        # EXECUTE QUERY
        # --------------------------------

        rows = list(client.query(query, job_config=job_config).result())

        print("rows are= ", rows)
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
                "name": row.get("NAME"),
                "email": row.get("PRIMARY_EMAIL"),
                "number": row.get("PHONE_NO"),
                "status": row.get("STATUS"),
               
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
    # function to normalize the call number, this should remove +  from the number if it is avaialble in the number
    def normalize_phone_number(number):
        number = str(number).strip()
        if number.startswith("+"):
            number = number[1:]
        return number

    #Gets list of recruiters the caller previously contacted
    def get_caller_recruiter_info(body):
        try:
            call_number = body.get("message", {}).get("customer", {}).get("number")
            tool_calls = body.get("message", {}).get("toolCalls", [])

            toll_call = tool_calls[0] if tool_calls else {}
            toll_call_id = toll_call.get("id")
            caller_name = toll_call.get("function", {}).get("arguments", {}).get("name", "")

            # caller_name = "Dev App"

            call_number = FeedbackHandler.normalize_phone_number(call_number)

            if not call_number:
                return jsonify({"error": "Internal Server Error"}), 500

            client = FeedbackHandler.create_bigquery_client()
            print("call number for query:", call_number)
            print("caller name for query:", caller_name)

            query = """
            SELECT
            external_number,
            internal_number,
            date_first_rang,
            email,
            name
            FROM (
            SELECT
                external_number,
                internal_number,
                date_first_rang,
                email,
                name,
                ROW_NUMBER() OVER (
                PARTITION BY email
                ORDER BY date_first_rang DESC
                ) AS rn
            FROM `{}.{}.{}`
            WHERE
                REGEXP_REPLACE(CAST(external_number AS STRING), r'[^0-9]', '')
                LIKE CONCAT('%', @call_number, '%')
                AND date_started >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
                AND LOWER(name) LIKE CONCAT('%', LOWER(@name), '%')
            )
            WHERE rn = 1
            """.format(
                FeedbackHandler.project_id,
                FeedbackHandler.call_data_project,
                FeedbackHandler.call_data_table
            )

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "call_number",
                        "STRING",
                        str(call_number)
                    ),
                    bigquery.ScalarQueryParameter(
                        "name",
                        "STRING",
                        str(caller_name)
                    )
                ]
            )
            
            results = client.query(query, job_config=job_config).result()

            
            print("result is", results)
            recruiter_data = [dict(row) for row in results]
            print("recruiter_data is", recruiter_data)

            # Second query to get text data
            text_data_query = """
            SELECT name,email
            FROM `cynetdatabase.ron_data_cluster.all_text_data`
            WHERE
                from_phone LIKE CONCAT('%', @call_number, '%')
                AND direction = 'internal'
                AND LOWER(name) LIKE CONCAT('%', LOWER(@name), '%')
                AND date >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
            """

            text_data_job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "call_number",
                        "STRING",
                        str(call_number)
                    ),
                    bigquery.ScalarQueryParameter(
                        "name",
                        "STRING",
                        str(caller_name)
                    )
                ]
            )

            text_data_results = client.query(text_data_query, job_config=text_data_job_config).result()
            text_data = [dict(row) for row in text_data_results]
            print("text_data is", text_data)

            # Combine both recruiter_data and text_data
            combined_data = recruiter_data + text_data
            print("combined_data is", combined_data)

            return jsonify({
                "results":[
                    {
                        "toolCallId": toll_call_id,
                        "result": {
                            "status": "success",
                            "message": "Recruiter identified successfully",
                            "data": combined_data
                        }
                    }
                ]
            }), 200

        except Exception as e:
            print("Error fetching recruiter info:", e)
            return jsonify({"error": "Internal Server Error"}), 500
        
    def send_message_to_Caller(body):
        print("Sending message to caller...")
        try:
            # Extract necessary information from the body
            call_number = body.get("message", {}).get("customer", {}).get("number")
            tool_call = body.get("message", {}).get("toolCalls", [])[0]
            args = tool_call["function"]["arguments"]
            recruiter_name = args.get("name")
            recruiter_email = args.get("email")
            recruiter_contact = args.get("internal number")

            message = (
                f"Hello, below is the recruiter details you were looking for:- \n\n"
                f"Name: {recruiter_name}\n"
                f"Email: {recruiter_email}\n"
                f"Contact: {recruiter_contact}\n"

            )

            # Here you would integrate with your messaging service to send the message
            # For example:
            # messaging_service.send_message(call_number, message)

            FeedbackHandler.sms_queue.put({
                "to": call_number,
                "text": message
            })
            print("Message queued to be sent to caller.")

            return jsonify({"status": "success"}), 200

        except Exception as e:
            print(f"Error sending message to caller: {e}")
            return jsonify({"error": "Internal Server Error"}), 500
