"""app/db.py - visitors + review decisions.

DATABASE_URL (env or Streamlit secret):
  local:       sqlite:///reviewer.db            (default)
  production:  postgresql://user:pass@host:5432/dbname   (Supabase / Neon / etc.)
Streamlit Community Cloud's disk is temporary, so use Postgres there.
"""
import functools
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (Column, Integer, MetaData, String, Table, Text,
                        create_engine, func, insert, select)

load_dotenv()
_md = MetaData()
visits = Table("visits", _md,
               Column("id", Integer, primary_key=True), Column(
                   "at", String(32)),
               Column("email", String(255)), Column("name", String(255)))
decisions = Table("decisions", _md,
                  Column("id", Integer, primary_key=True), Column(
                      "at", String(32)),
                  Column("reviewer_email", String(255)), Column(
                      "reviewer_name", String(255)),
                  Column("document", String(255)), Column(
                      "finding_id", Integer),
                  Column("section", String(255)), Column(
                      "category", String(64)),
                  Column("severity", String(16)), Column("action", String(16)),
                  Column("original_text", Text), Column("edited_text", Text))
_engine = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL") or "sqlite:///reviewer.db"
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _engine = create_engine(url, pool_pre_ping=True)
        _md.create_all(_engine)
    return _engine


def _safe(default):
    """A database problem must never crash the review UI."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            try:
                return fn(*a, **kw)
            except Exception as e:
                print(f"[db] {fn.__name__} failed: {e}", file=sys.stderr)
                return default
        return wrapper
    return deco


@_safe(None)
def log_visit(email: str, name: str):
    with _get_engine().begin() as c:
        c.execute(insert(visits).values(at=_now(), email=email, name=name))


@_safe(None)
def save_decision(**kw):
    with _get_engine().begin() as c:
        c.execute(insert(decisions).values(at=_now(), **kw))


def _rows(stmt):
    with _get_engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(stmt)]


@_safe([])
def list_decisions(email=None, limit=2000):
    s = select(decisions).order_by(decisions.c.id.desc()).limit(limit)
    if email:
        s = s.where(decisions.c.reviewer_email == email)
    return _rows(s)


@_safe([])
def visitors_summary():
    return _rows(select(
        visits.c.email, func.max(visits.c.name).label("name"),
        func.count().label("visits"), func.min(visits.c.at).label("first_seen"),
        func.max(visits.c.at).label("last_seen"),
    ).group_by(visits.c.email).order_by(func.max(visits.c.at).desc()))


@_safe([])
def recent_visits(limit=50):
    return _rows(select(visits).order_by(visits.c.id.desc()).limit(limit))
