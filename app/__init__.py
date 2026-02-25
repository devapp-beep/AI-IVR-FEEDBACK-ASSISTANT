from flask import Flask

def create_app():
    app = Flask(__name__)

    # Import and register blueprints INSIDE create_app
    try:
        from .routes.health_controller import health_bp
        from .routes.vapi_feedback_controller import vapi_feedback_bp
        from .routes.vapi_recruiter_info import vapi_recruiter_info_bp
        from .routes.vapi_caller_recruiter_details_info import vapi_caller_recruiter_details_info_bp
        from .routes.vapi_recruiter_infomation_message import vapi_recruiter_infomation_message
        from .routes.twilio_webhook_controller import twilio_webhook_bp
        app.register_blueprint(health_bp)          # -> /health
        app.register_blueprint(vapi_feedback_bp)     # -> /user_feedback
        app.register_blueprint(vapi_recruiter_info_bp)     # -> /recruiter_info
        app.register_blueprint(vapi_caller_recruiter_details_info_bp)  # -> /caller_recruiter_details_info
        app.register_blueprint(vapi_recruiter_infomation_message)  # -> /recruiter_info_message
        app.register_blueprint(twilio_webhook_bp)  # -> /twilio/incoming
        # If you want an /api prefix: app.register_blueprint(vapi_bp, url_prefix="/api")
    except Exception as e:
        print("\n[IMPORT ERROR] Couldn't register blueprints:", e, "\n")

    # Debug: list routes
    print("\n=== URL MAP ===")
    for rule in app.url_map.iter_rules():
        print(rule)
    print("===============\n")
    print("Registered blueprints:", list(app.blueprints.keys()))
    return app
