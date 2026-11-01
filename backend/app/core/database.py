import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../p2p.db")
if DATABASE_URL.startswith("sqlite"):
    db_path = DATABASE_URL.removeprefix("sqlite:///")
    if db_path != ":memory:":
        absolute = (Path(__file__).resolve().parents[2] / db_path).resolve()
        absolute.parent.mkdir(parents=True, exist_ok=True)
        DATABASE_URL = f"sqlite:///{absolute.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
