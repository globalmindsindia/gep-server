# app.py
from flask import Flask, jsonify
from sqlalchemy import text
from config.config import Config
from db.database import init_db, auto_migrate
from utils.email_service import init_mail
from routes.register import bp as register_bp
from flask_cors import CORS

def create_app():
    app = Flask(__name__)

    # Load config values from Config
    app.config["DEBUG"] = Config.DEBUG
    app.config["FROM_EMAIL"] = Config.FROM_EMAIL
    app.config["ADMIN_EMAIL"] = Config.ADMIN_EMAIL

    # Flask-Mail config
    app.config["MAIL_SERVER"] = Config.MAIL_SERVER
    app.config["MAIL_PORT"] = Config.MAIL_PORT
    app.config["MAIL_USERNAME"] = Config.MAIL_USERNAME
    app.config["MAIL_PASSWORD"] = Config.MAIL_PASSWORD
    app.config["MAIL_USE_TLS"] = Config.MAIL_USE_TLS
    app.config["MAIL_USE_SSL"] = Config.MAIL_USE_SSL
    # Prefer NO_REPLY_EMAIL as the default for outgoing system messages when configured
    app.config["MAIL_DEFAULT_SENDER"] = Config.NO_REPLY_EMAIL or Config.FROM_EMAIL

    # CORS
    CORS(app, origins=Config.ALLOWED_ORIGINS, supports_credentials=True)

    # Ensure DB schema exists and apply safe auto-migrations (adds missing tables/columns)
    # auto_migrate internally uses Base.metadata.create_all() and ALTER TABLE to add missing columns.
    try:
        auto_migrate()
    except Exception:
        # Fallback to init_db if auto_migrate isn't available or fails for some reason
        app.logger.exception("auto_migrate failed, falling back to init_db()")
        init_db()

    # init mail
    init_mail(app)

    # register blueprints
    app.register_blueprint(register_bp)

    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/health/db", methods=["GET"])
    def health_db():
        """Simple DB health check endpoint.
        Returns 200 if DB is reachable and a basic select 1 works, otherwise returns 503.
        """
        from db.database import engine
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return jsonify({"db": "ok"})
        except Exception as e:
            app.logger.exception("DB health check failed: %s", e)
            return jsonify({"db": "error", "error": str(e)}), 503

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=Config.APP_HOST, port=Config.APP_PORT, debug=Config.DEBUG)
