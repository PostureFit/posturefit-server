import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# ---------------------------------------------------------------------------
# Database URL — dibaca dari .env (wajib diatur)
# ---------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL belum diatur di file .env!")


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,      # Auto-reconnect on stale connections
    pool_size=10,             # Keep up to 10 persistent connections
    max_overflow=20,          # Allow up to 20 additional connections under load
    echo=False,               # Set True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency  –  yields a DB session per request and always closes it.
# ---------------------------------------------------------------------------
def get_db():
    """Dependency that provides a SQLAlchemy session for the duration of a
    single request, then closes it to prevent connection leaks."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()