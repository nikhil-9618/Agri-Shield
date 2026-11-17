"""Database engine, session factory and ORM models.

Sqlite is the default for zero-setup development; set DATABASE_URL to a
PostgreSQL URL for the production configuration (database/schema.sql mirrors the
same tables). No table is created with secrets or personal data beyond what the
farmer chooses to enter.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Generator

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="te", nullable=False)
    village: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    detections: Mapped[list["Detection"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    crop_key: Mapped[str] = mapped_column(String(40), nullable=False)
    disease_key: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # green | yellow | red
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # diagnosed | unclear
    language: Mapped[str] = mapped_column(String(5), default="te", nullable=False)
    top3: Mapped[dict] = mapped_column(JSON, default=list)
    advisory_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    gradcam_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(60), default="unknown")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    user: Mapped[User] = relationship(back_populates="detections")


def init_db() -> None:
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
