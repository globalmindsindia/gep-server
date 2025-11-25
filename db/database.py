# db/database.py
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config.config import Config

# Create engine
engine_args = {}
if Config.DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(Config.DATABASE_URL, echo=False, **engine_args)

# Session
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

def init_db():
    """Create all tables if not exist (basic version)."""
    from models.user import Base
    Base.metadata.create_all(bind=engine)


# -------------------------------------------------------------
#           SAFE AUTO-MIGRATION (CREATE / PATCH)
# -------------------------------------------------------------
def auto_migrate():
    """
    Auto-creates missing tables AND auto-adds missing columns.
    Does NOT delete data. Safe for local & lightweight usage.
    """
    from models.user import Base, User  # import models

    inspector = inspect(engine)

    # 1) Ensure table exists
    Base.metadata.create_all(bind=engine)

    # 2) Required columns for auto-add
    required_columns = {
        "id": "INTEGER",
        "name": "VARCHAR(200)",
        "email": "VARCHAR(255)",
        "mobile": "VARCHAR(20)",
        "qualification": "VARCHAR(200)",
        "experience": "TEXT",
        "extra": "TEXT",
        "created_at": "DATETIME"
    }

    # Fetch existing columns; if table doesn't exist inspector.get_columns will raise,
    # but create_all above ensures it exists.
    existing_cols = [col["name"] for col in inspector.get_columns("users")]

    # 3) Add missing columns inside a transaction (engine.begin ensures commit)
    with engine.begin() as conn:
        for col_name, col_type in required_columns.items():
            if col_name not in existing_cols:
                print(f"[AUTO-MIGRATE] Adding missing column: {col_name}")
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))

    print("[AUTO-MIGRATE] Schema verified/updated.")

