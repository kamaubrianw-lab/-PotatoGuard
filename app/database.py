"""
app/database.py
===============
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
# Load .env for local development
# Render and Supabase inject DATABASE_URL directly as an env var —
# load_dotenv() is a no-op in production (env var already set)
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# DATABASE_URL — switches automatically between SQLite and PostgreSQL
#
# Local dev  : leave DATABASE_URL unset → SQLite file is used
# Production : set DATABASE_URL in Render to your Supabase connection string
#
# Supabase connection string format (from Supabase dashboard → Settings → Database):
#   postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-REF].supabase.co:5432/postgres
#
# CRITICAL FIX: Some providers (Heroku, older Supabase) return URLs starting
# with "postgres://" — SQLAlchemy 2.0 requires "postgresql://"
# The line below fixes this automatically.
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{_ROOT / 'potato_disease.db'}",
)

# Fix legacy "postgres://" prefix — SQLAlchemy 2.0 requires "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ---------------------------------------------------------------------------
# Engine — different configuration for SQLite vs PostgreSQL
# ---------------------------------------------------------------------------
if _IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite only
        echo=False,
    )
else:
    # PostgreSQL — connection pooling for production resilience
    # pool_pre_ping reconnects automatically if a connection goes stale
    # (common with Supabase which closes idle connections after ~5 minutes)
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,   # recycle connections every 5 mins
        echo=False,
    )


@event.listens_for(engine, "connect")
def _configure_connection(dbapi_conn, _record) -> None:
    """
    SQLite only: enable WAL mode + foreign key enforcement.
    PostgreSQL handles both of these natively — no action needed.
    """
    if _IS_SQLITE:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Declarative base (SQLAlchemy 2.0 Mapped style)
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(Base):
    """
    Registered users.
    Login identifier : email  (unique, indexed)
    Roles            : 'user' | 'admin'
    """
    __tablename__ = "users"

    id             : Mapped[int]      = mapped_column(primary_key=True, index=True)
    email          : Mapped[str]      = mapped_column(
                                            String(255), unique=True,
                                            index=True, nullable=False)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    role           : Mapped[str]      = mapped_column(String(50), default="user")
    created_at     : Mapped[datetime] = mapped_column(
                                            DateTime(timezone=True),
                                            default=lambda: datetime.now(timezone.utc),
                                            nullable=False)

    scans: Mapped[List["ScanHistory"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User email={self.email!r} role={self.role!r}>"


class ScanHistory(Base):
    """One row per leaf-image scan submitted by a user."""
    __tablename__ = "scan_history"

    id              : Mapped[int]           = mapped_column(primary_key=True, index=True)
    user_id         : Mapped[int]           = mapped_column(
                                                 ForeignKey("users.id", ondelete="CASCADE"),
                                                 nullable=False, index=True)
    email           : Mapped[str]           = mapped_column(
                                                 String(255), nullable=False, index=True)
    disease_type    : Mapped[str]           = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float]         = mapped_column(Float, nullable=False)
    llm_advice      : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_path      : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    timestamp       : Mapped[datetime]      = mapped_column(
                                                 DateTime(timezone=True),
                                                 default=lambda: datetime.now(timezone.utc),
                                                 nullable=False)

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
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a Session and guarantees cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()