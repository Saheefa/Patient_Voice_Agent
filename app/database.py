"""
Database configuration.

Local/dev default: SQLite file (patients.db) — zero setup, persists to disk.
Production (Vercel): Vercel's filesystem is ephemeral/read-only across
invocations, so SQLite does NOT persist there. Set DATABASE_URL to a hosted
Postgres instance (e.g. Vercel Postgres / Neon / Supabase) in production and
this module will use it automatically.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./patients.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Vercel Postgres / Neon / Supabase URLs sometimes use the "postgres://" scheme,
# which SQLAlchemy's psycopg driver no longer accepts — normalize it.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
