"""SQLAlchemy database configuration and models for the HR Screening Web App (T016, T018, T019).

Uses SQLite by default at screening_webapp/data/app.db, configurable via DATABASE_URL
so Cloud SQL can be switched in later without code changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

WEBAPP_DIR = Path(__file__).resolve().parent
DATA_DIR = WEBAPP_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "app.db"


class Base(DeclarativeBase):
    """Declarative base for all screening_webapp models."""


class Job(Base):
    """Job posting configuration and uploaded file paths (T019)."""

    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    jd_filename = Column(String(255), nullable=False, default="")
    jd_path = Column(Text, nullable=False)
    applications_dir = Column(Text, nullable=False)
    threshold = Column(Float, nullable=False, default=70.0)
    requires_continuity = Column(Boolean, nullable=False, default=False)
    model = Column(String(64), nullable=False, default="gemini-4-argon")
    created_at_utc = Column(String(64), nullable=False)
    created_by_email = Column(String(255), nullable=False, default="system")


class Run(Base):
    """Screening run metadata and status, linked to a Job."""

    __tablename__ = "runs"

    id = Column(String(64), primary_key=True, index=True)
    job_id = Column(String(64), ForeignKey("jobs.job_id"), nullable=True, index=True)
    started_at = Column(String(64), nullable=False)
    finished_at = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, index=True)
    settings_json = Column(Text, nullable=False, default="{}")
    model = Column(String(64), nullable=False)
    threshold = Column(Float, nullable=False, default=70.0)
    candidate_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)


class CandidateResult(Base):
    """Per-candidate evaluation stored for a specific screening run and job."""

    __tablename__ = "candidate_results"

    run_id = Column(String(64), ForeignKey("runs.id"), primary_key=True, index=True)
    candidate_id = Column(String(32), primary_key=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    ai_decision = Column(String(64), nullable=False)
    ai_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(64), nullable=False)
    review_reasons_json = Column(Text, nullable=False, default="[]")
    evidence_json = Column(Text, nullable=False, default="{}")


class HrDecision(Base):
    """HR decision history keyed by (job_id, candidate_id); the latest row per pair is active."""

    __tablename__ = "hr_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), nullable=False, default="JOB-2026-001", index=True)
    candidate_id = Column(String(32), nullable=False, index=True)
    run_id = Column(String(64), nullable=True, index=True)
    decision = Column(String(64), nullable=False)
    note = Column(Text, nullable=False, default="")
    decided_by_email = Column(String(255), nullable=False)
    decided_at_utc = Column(String(64), nullable=False)


class AuditLog(Base):
    """Immutable audit log of HR and Admin actions (runs, settings, decisions, access control)."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    at_utc = Column(String(64), nullable=False, index=True)
    actor_email = Column(String(255), nullable=False, index=True)
    action = Column(String(128), nullable=False)
    detail = Column(Text, nullable=False, default="")


class AllowedUser(Base):
    """Database-backed allow-list of authorised users and their roles (admin | hr) (T018)."""

    __tablename__ = "allowed_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    role = Column(String(32), nullable=False, default="hr")
    added_by = Column(String(255), nullable=False, default="system")
    added_at_utc = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class AllowedDomain(Base):
    """Database-backed allow-list of organisation domains (e.g. 'example.gov') (T018)."""

    __tablename__ = "allowed_domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False, unique=True, index=True)
    role = Column(String(32), nullable=False, default="hr")
    added_by = Column(String(255), nullable=False, default="system")
    added_at_utc = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


_ENGINE = None
_ENGINE_URL: str | None = None
_SESSION_LOCAL = None


def get_database_url() -> str:
    """Return DATABASE_URL from environment or default to screening_webapp/data/app.db."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url and env_url.strip():
        return env_url.strip()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB_PATH}"


def _ensure_sqlite_columns(engine) -> None:
    """Ensure new columns (such as job_id) exist on existing SQLite tables."""
    if not str(engine.url).startswith("sqlite"):
        return
    migrations = [
        ("runs", "job_id", "VARCHAR(64)"),
        ("candidate_results", "job_id", "VARCHAR(64)"),
        ("hr_decisions", "job_id", "VARCHAR(64) DEFAULT 'JOB-2026-001'"),
    ]
    with engine.begin() as conn:
        for table_name, col_name, col_type in migrations:
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            existing_cols = {r[1] for r in rows}
            if existing_cols and col_name not in existing_cols:
                conn.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                )


def get_engine():
    """Return (and initialize if needed) the SQLAlchemy engine for the current DATABASE_URL."""
    global _ENGINE, _ENGINE_URL, _SESSION_LOCAL
    url = get_database_url()
    if _ENGINE is None or _ENGINE_URL != url:
        if url.startswith("sqlite:///"):
            sqlite_path = url.replace("sqlite:///", "", 1)
            if sqlite_path and sqlite_path != ":memory:":
                Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {}
        _ENGINE = create_engine(url, connect_args=connect_args, future=True)
        _ENGINE_URL = url
        _SESSION_LOCAL = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE, future=True)
        Base.metadata.create_all(bind=_ENGINE)
        _ensure_sqlite_columns(_ENGINE)
    return _ENGINE


def init_db() -> None:
    """Ensure all database tables and migrated columns are created."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns(engine)


def get_session() -> Session:
    """Create a new SQLAlchemy Session bound to the current engine."""
    get_engine()
    assert _SESSION_LOCAL is not None
    return _SESSION_LOCAL()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session and closes it afterwards."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()
