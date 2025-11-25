# config/config.py
import os
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

class Config:
    # --- App settings ---
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8000))

    # --- CORS Settings ---
    # Accept comma-separated values: e.g., "http://localhost:3000,http://127.0.0.1:3000"
    ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    ]

    # --- Email / Admin ---
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    FROM_EMAIL = os.getenv("FROM_EMAIL")  # Same as MAIL_DEFAULT_SENDER
    NO_REPLY_EMAIL = os.getenv("NO_REPLY_EMAIL")

    # --- SMTP / Flask-Mail Settings ---
    # Your provider-specific SMTP host and port must be placed in .env
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))

    # These come from your SMTP credentials / API key
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")  # e.g. "emailapikey"
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")  # your long encoded key

    # TLS/SSL flags
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes")

    # Default sender used by Flask-Mail - prefer NO_REPLY_EMAIL if set
    MAIL_DEFAULT_SENDER = os.getenv("NO_REPLY_EMAIL") or os.getenv("FROM_EMAIL")

    # --- Database ---
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
