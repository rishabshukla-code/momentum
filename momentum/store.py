"""Storage. SQLite locally; point DATABASE_URL at SingleStore for the live data loop.

Always order by time, not id: SingleStore auto-increment ids are unique but not in time order.

Tables:
  users   - one row per Telegram chat
  tasks   - what the user wants to work on
  nudges  - every nudge sent, the reason it was chosen, and its outcome
            (this is both the agent's state and its telemetry)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Integer, MetaData, String, Table, Text,
    and_, create_engine, insert, or_, select, update,
)

from . import config
from .brain import Outcome

def make_engine(url: str):
    """SQLite locally; SingleStore (MySQL protocol) over TLS when the URL is mysql://."""
    if url.startswith("mysql"):
        import certifi  # ships with httpx

        return create_engine(url, future=True, pool_pre_ping=True, pool_recycle=280,
                             connect_args={"ssl": {"ca": certifi.where()}})
    return create_engine(url, future=True)


engine = make_engine(config.DATABASE_URL)
meta = MetaData()
# SingleStore auto-increment values are large; SQLite needs INTEGER for its rowid alias.
ID = BigInteger().with_variant(Integer, "sqlite")

users = Table(
    "users", meta,
    Column("chat_id", String(64), primary_key=True),
    Column("name", String(128)),
    Column("onboarding", String(64)),
    Column("created_at", DateTime),
)

tasks = Table(
    "tasks", meta,
    Column("id", ID, primary_key=True, autoincrement=True),
    Column("chat_id", String(64), index=True),
    Column("title", String(255)),
    Column("deadline", String(64)),
    Column("active", Boolean, default=True),
    Column("created_at", DateTime),
)

nudges = Table(
    "nudges", meta,
    Column("id", ID, primary_key=True, autoincrement=True),
    Column("chat_id", String(64), index=True),
    Column("task_id", ID),
    Column("arm", String(32)),
    Column("context", String(32)),
    Column("text", Text),
    Column("reason", Text),
    Column("sent_at", DateTime),
    Column("outcome", String(16)),  # None (waiting) | started | snoozed | ignored
    Column("responded_at", DateTime),
    Column("excuse", String(32)),
    Column("message_id", String(64)),
)


def init_db() -> None:
    meta.create_all(engine)


def upsert_user(chat_id: str, name: str) -> None:
    with engine.begin() as c:
        if not c.execute(select(users).where(users.c.chat_id == chat_id)).first():
            c.execute(insert(users).values(chat_id=chat_id, name=name, created_at=datetime.now()))


def set_onboarding(chat_id: str, answer: str) -> None:
    with engine.begin() as c:
        c.execute(update(users).where(users.c.chat_id == chat_id).values(onboarding=answer))


def get_user(chat_id: str):
    with engine.begin() as c:
        return c.execute(select(users).where(users.c.chat_id == chat_id)).mappings().first()


def all_users():
    with engine.begin() as c:
        return list(c.execute(select(users)).mappings())


def add_task(chat_id: str, title: str, deadline: str | None) -> int:
    with engine.begin() as c:
        c.execute(update(tasks).where(tasks.c.chat_id == chat_id).values(active=False))
        r = c.execute(insert(tasks).values(
            chat_id=chat_id, title=title, deadline=deadline, active=True,
            created_at=datetime.now()))
        return r.inserted_primary_key[0]


def active_task(chat_id: str):
    with engine.begin() as c:
        return c.execute(
            select(tasks).where(tasks.c.chat_id == chat_id, tasks.c.active.is_(True))
            .order_by(tasks.c.created_at.desc(), tasks.c.id.desc())
        ).mappings().first()


def finish_task(chat_id: str) -> None:
    with engine.begin() as c:
        c.execute(update(tasks).where(tasks.c.chat_id == chat_id).values(active=False))


def log_nudge(chat_id, task_id, arm, context, text, reason) -> int:
    with engine.begin() as c:
        r = c.execute(insert(nudges).values(
            chat_id=chat_id, task_id=task_id, arm=arm, context=context, text=text,
            reason=reason, sent_at=datetime.now()))
        return r.inserted_primary_key[0]


def get_nudge(nudge_id: int):
    with engine.begin() as c:
        return c.execute(select(nudges).where(nudges.c.id == nudge_id)).mappings().first()


def delete_nudge(nudge_id: int) -> None:
    with engine.begin() as c:
        c.execute(nudges.delete().where(nudges.c.id == nudge_id))


def set_message_id(nudge_id: int, message_id: str) -> None:
    with engine.begin() as c:
        c.execute(update(nudges).where(nudges.c.id == nudge_id).values(message_id=message_id))


def resolve(nudge_id: int, outcome: str, excuse: str | None = None):
    """Set the outcome once. Returns the row, or None if it was already resolved."""
    with engine.begin() as c:
        row = c.execute(select(nudges).where(nudges.c.id == nudge_id)).mappings().first()
        if not row or row["outcome"]:
            return None
        c.execute(update(nudges).where(nudges.c.id == nudge_id).values(
            outcome=outcome, responded_at=datetime.now(), excuse=excuse))
        return dict(row) | {"outcome": outcome}


def set_excuse(nudge_id: int, excuse: str) -> None:
    with engine.begin() as c:
        c.execute(update(nudges).where(nudges.c.id == nudge_id).values(excuse=excuse))


def last_nudge(chat_id: str):
    with engine.begin() as c:
        return c.execute(
            select(nudges).where(nudges.c.chat_id == chat_id).order_by(nudges.c.sent_at.desc(), nudges.c.id.desc())
        ).mappings().first()


def nudges_for_task(task_id: int) -> int:
    with engine.begin() as c:
        # a "later" (deferred) answer doesn't use up one of the nudges for this task
        return len(list(c.execute(select(nudges.c.id).where(
            nudges.c.task_id == task_id, or_(nudges.c.outcome.is_(None), nudges.c.outcome != "deferred")))))


def expire_waiting(window_min: int) -> list[dict]:
    """Mark nudges with no reply after the window as ignored (a miss)."""
    cutoff = datetime.now() - timedelta(minutes=window_min)
    # a Momentum Phone call can ring for 20s and then talk, so give it at least 3 minutes
    call_cutoff = datetime.now() - timedelta(minutes=max(window_min, 3))
    is_call = nudges.c.message_id == "web"
    with engine.begin() as c:
        rows = list(c.execute(
            select(nudges).where(nudges.c.outcome.is_(None), or_(
                and_(or_(nudges.c.message_id.is_(None), ~is_call), nudges.c.sent_at < cutoff),
                and_(is_call, nudges.c.sent_at < call_cutoff)))
        ).mappings())
        for r in rows:
            c.execute(update(nudges).where(nudges.c.id == r["id"]).values(
                outcome="ignored", responded_at=datetime.now()))
    return [dict(r) for r in rows]


def history(chat_id: str | None = None) -> list[Outcome]:
    # "deferred" (they asked to wait) is neither a win nor a miss for that nudge type
    q = select(nudges).where(nudges.c.outcome.is_not(None), nudges.c.outcome != "deferred")
    if chat_id:
        q = q.where(nudges.c.chat_id == chat_id)
    with engine.begin() as c:
        return [
            Outcome(r["arm"], r["context"], r["outcome"] == "started", r["sent_at"])
            for r in c.execute(q).mappings()
        ]


def recent_nudges(limit: int = 50) -> list[dict]:
    with engine.begin() as c:
        return [dict(r) for r in c.execute(
            select(nudges).order_by(nudges.c.sent_at.desc(), nudges.c.id.desc()).limit(limit)).mappings()]


def streak(chat_id: str) -> int:
    """Number of 'started' outcomes in a row, most recent first."""
    with engine.begin() as c:
        rows = c.execute(
            select(nudges.c.outcome).where(nudges.c.chat_id == chat_id,
                                           nudges.c.outcome.is_not(None))
            .order_by(nudges.c.sent_at.desc(), nudges.c.id.desc()).limit(20)
        ).scalars()
        n = 0
        for o in rows:
            if o == "deferred":
                continue
            if o != "started":
                break
            n += 1
        return n
