from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
import os

import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger("DatabaseConnection")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.db")
SQLITE_URL = f"sqlite:///{DB_PATH}"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", SQLITE_URL)

# ── Render/Supabase Compatibility Fix ────────────────────────────────────────
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Check for placeholder or broken configuration
if "YOURPROJECT" in SQLALCHEMY_DATABASE_URL or "placeholder" in SQLALCHEMY_DATABASE_URL:
    logger.warning("DATABASE_URL contains placeholder. Defaulting to local SQLite WAL database.")
    SQLALCHEMY_DATABASE_URL = SQLITE_URL

# Attempt connection to remote DB if configured; fall back gracefully to SQLite if unreachable
is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
if not is_sqlite:
    try:
        test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"connect_timeout": 3})
        with test_engine.connect() as test_conn:
            pass
        test_engine.dispose()
    except Exception as db_err:
        logger.warning(f"Remote database unreachable ({db_err}). Gracefully falling back to local SQLite.")
        SQLALCHEMY_DATABASE_URL = SQLITE_URL
        is_sqlite = True

connect_args = {}
if is_sqlite:
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,
    }

engine_kwargs: dict = {"connect_args": connect_args}
if is_sqlite:
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

# Enable WAL mode for SQLite only — prevents lock storms
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if engine.url.get_backend_name() == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
