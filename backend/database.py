import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default to SQLite for local rapid dev if Postgres isn't ready
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./enterprise_platform.db")

# SQLite requires specific arguments to prevent thread-sharing issues
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency Injection for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()