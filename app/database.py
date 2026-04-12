"""
app/database.py
===============

Schema
------
  User        : id, email (unique login), hashed_password, role, created_at
  ScanHistory : id, user_id (FK), email, disease_type, confidence_score,
                llm_advice, timestamp, image_path
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from sqlalchemy import (
    DateTime, Float, ForeignKey,
    String, Text, create_engine, event,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, Session,
    mapped_column, relationship, sessionmaker,
)

# ---------------------------------------------------------------------------
# Load .env — must happen before reading DATABASE_URL
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent          # potato_disease_app/
load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{_ROOT / 'potato_disease.db'}",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_pragmas(dbapi_conn, _record) -> None:
    """
    Enable WAL mode + foreign keys on every new SQLite connection.
    WAL mode prevents 'database is locked' when Streamlit reads
    simultaneously while FastAPI writes.
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Declarative base  (SQLAlchemy 2.0 style)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models — using Mapped[T] + mapped_column() throughout
# ---------------------------------------------------------------------------
class User(Base):
    """
    Registered users.
    Login identifier : email  (unique, indexed)
    Roles            : 'user' | 'admin'
    """

    __tablename__ = "users"

    id             : Mapped[int]      = mapped_column(primary_key=True, index=True)
    email          : Mapped[str]      = mapped_column(String(255), unique=True,
                                                      index=True, nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    role           : Mapped[str]      = mapped_column(String(50),  default="user")
    created_at     : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    scans: Mapped[List["ScanHistory"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User email={self.email!r} role={self.role!r}>"


class ScanHistory(Base):
    """One row per leaf-image scan submitted by a user."""

    __tablename__ = "scan_history"

    id              : Mapped[int]            = mapped_column(primary_key=True, index=True)
    user_id         : Mapped[int]            = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email           : Mapped[str]            = mapped_column(String(255),
                                                              nullable=False, index=True)
    disease_type    : Mapped[str]            = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float]          = mapped_column(Float,       nullable=False)
    llm_advice      : Mapped[Optional[str]]  = mapped_column(Text,        nullable=True)
    image_path      : Mapped[Optional[str]]  = mapped_column(String(500), nullable=True)
    timestamp       : Mapped[datetime]       = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    owner: Mapped["User"] = relationship(back_populates="scans")

    def __repr__(self) -> str:
        return (
            f"<ScanHistory id={self.id} email={self.email!r} "
            f"disease={self.disease_type!r} confidence={self.confidence_score:.2%}>"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create all tables (idempotent). Called once on FastAPI startup."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a Session and guarantees cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()