from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator
from app.core.config import settings

# For SQLite, we must set connect_args={"check_same_thread": False}
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False  # Set to True for debugging SQL queries if needed
)

# SQLite does not enforce foreign keys by default. Enforce them on connection.
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# SessionLocal is the factory for DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import declarative base class from models to unify the metadata registry
from app.models.base import Base


def get_db() -> Generator:
    """
    FastAPI dependency that provides a transactional database session.
    Automatically closes the session after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
