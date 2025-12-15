from flask import Flask
from logging_config import setup_logger

logger = setup_logger("app")

def create_app():
    app = Flask(__name__)
    app.secret_key = "supersecretkey"

    from auth import bp as auth_bp
    from routes_config import bp as config_bp
    from routes_alarms import bp as alarms_bp
    from routes_view import bp as view_bp

    from routes.alarmes import bp as alarm_bp
    from routes.reset import bp as reset_bp
    from routes.api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(view_bp)
    app.register_blueprint(alarm_bp)
    app.register_blueprint(reset_bp)
    app.register_blueprint(api_bp)

    logger.info("WebServer iniciado")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=True)
