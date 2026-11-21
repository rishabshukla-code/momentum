"""Planner page: type what's coming up, Momentum files it and schedules the calls.

Routes (served by server.py; open on this laptop, token needed through the public link):
  GET    /plan                      the page
  GET    /plan/api/events           saved events with their schedule and next call
  POST   /plan/api/events           {"text": "Mom's birthday Nov 20"} -> saved event
  DELETE /plan/api/events/{id}      remove an event
  POST   /plan/api/events/{id}/ring call me about this event right now (Momentum Phone)
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from . import events, store
from .webphone import _check

router = APIRouter(prefix="/plan")
PAGE = Path(__file__).with_name("planner.html")


def _owner() -> str:
    """The person using this laptop: the first real (non-demo) user."""
    users = [u for u in store.all_users() if not u["chat_id"].startswith("demo-")]
    if not users:
        raise HTTPException(409, "Send /start to the Telegram bot once first.")
    return sorted(users, key=lambda u: u["created_at"] or datetime.min)[0]["chat_id"]


def _when(dt: datetime | None) -> str:
    if not dt:
        return "no more calls planned"
    today = date.today()
    day = ("today" if dt.date() == today else "tomorrow" if (dt.date() - today).days == 1
           else f"{dt:%a %b} {dt.day}" + (f", {dt.year}" if dt.year != today.year else ""))
    return f"{day} at {dt:%I:%M %p}".replace(" 0", " ")


def _view(ev: dict) -> dict:
    cat = events.CATEGORIES.get(ev["category"], events.CATEGORIES["task"])
    rep = {"yearly": "Every year", "monthly": "Every month", "weekly": "Every week",
           "daily": "Every day", "none": "Once"}[ev["repeat"]]
    if ev.get("date") and ev["repeat"] != "daily":
        d = date.fromisoformat(ev["date"])
        rep += f" on {d:%b} {d.day}"
    times = [ev["time"]] if ev.get("time") and cat["repeat"] == "none" else cat["at"]
    pretty = ", ".join(datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0") for t in times)
    lead = cat["lead_days"]
    calls = ("on the day" if lead == [0] else
             ", ".join("on the day" if x == 0 else ("1 day before" if x == 1 else f"{x} days before") for x in lead))
    nxt = events.next_call(ev)
    due_now = any(e["id"] == ev["id"] for e, _, _ in events.due())
    return {"id": ev["id"], "title": ev["title"], "emoji": cat["emoji"], "label": cat["label"],
            "schedule": rep, "calls": f"Calls {calls} · {pretty}",
            "next": "calling you now" if due_now else _when(nxt), "due_now": due_now}


@router.get("", response_class=HTMLResponse)
def page(request: Request, k: str = ""):
    _check(k, request)
    return PAGE.read_text(encoding="utf-8")


@router.get("/api/events")
def list_events(request: Request, k: str = ""):
    _check(k, request)
    mine = events.for_chat(_owner())
    mine.sort(key=lambda e: events.next_call(e) or datetime.max)
    return {"events": [_view(e) for e in mine]}


@router.post("/api/events")
async def add_event(request: Request, k: str = ""):
    _check(k, request)
    text = str((await request.json()).get("text", "")).strip()[:300]
    if not text:
        raise HTTPException(400, "Type something first")
    ev = await run_in_threadpool(events.add, _owner(), text)  # Claude files it (about 2 s)
    return {"event": _view(ev)}


@router.delete("/api/events/{event_id}")
def delete_event(request: Request, event_id: str, k: str = ""):
    _check(k, request)
    ev = events.remove(_owner(), event_id)
    if not ev:
        raise HTTPException(404, "No such event")
    return {"removed": ev["title"]}


@router.post("/api/events/{event_id}/ring")
async def ring_now(request: Request, event_id: str, k: str = ""):
    _check(k, request)
    from . import agent, voice

    owner = _owner()
    ev = next((e for e in events.for_chat(owner) if e["id"] == event_id), None)
    if not ev:
        raise HTTPException(404, "No such event")
    occ = events.next_occurrence(ev, date.today())
    days_left = (occ - date.today()).days if occ else 0
    title, when = events.task_for(ev, days_left)
    store.add_task(owner, title, when)
    voice.set_call(owner, "web")
    r = await run_in_threadpool(agent.send_nudge, owner)
    return {"ringing": bool(r), "task": title, "text": r and r["text"]}
