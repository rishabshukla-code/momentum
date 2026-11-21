"""Scheduled events: birthdays, exams, bills, medicine... each saved as JSON with a category.

The category (categories.json) decides WHEN Momentum calls:
  birthday  -> every year, 9:00 on the day
  exam      -> 21, 14, 7, 3 and 1 days before, 19:00
  medicine  -> every day, 09:00   ... and so on.

You just type "/add Mom's birthday Nov 20"; Claude works out the category, title, person
and date (keyword rules + a date parser are the fallback). Events live in events.json:

  {"id": "e3f1", "chat_id": "780...", "title": "Mom's birthday", "category": "birthday",
   "person": "Mom", "date": "2026-11-20", "time": null, "repeat": "yearly",
   "created_at": "2026-11-20T16:40:00", "fired": ["2026-11-20@0d@09:00"]}

The agent's timer asks due() for reminders that are due and turns each into a call.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path

from . import config

log = logging.getLogger("momentum")
ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = {k: v for k, v in json.loads(
    (Path(__file__).with_name("categories.json")).read_text(encoding="utf-8")).items() if not k.startswith("_")}
EVENTS_FILE = ROOT / "events.json"
GRACE = timedelta(hours=12)  # a reminder missed by more than this (laptop off) is skipped
REPEATS = ["none", "yearly", "monthly", "weekly", "daily"]


# ---------------------------------------------------------------- storage
def load() -> list[dict]:
    try:
        return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save(events: list[dict]) -> None:
    EVENTS_FILE.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")


def for_chat(chat_id: str) -> list[dict]:
    return [e for e in load() if e["chat_id"] == str(chat_id)]


def remove(chat_id: str, event_id: str) -> dict | None:
    events = load()
    for e in events:
        if e["chat_id"] == str(chat_id) and e["id"] == event_id:
            events.remove(e)
            save(events)
            return e
    return None


# ---------------------------------------------------------------- understanding text
SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "title": {"type": "string", "description": "short name of the event, e.g. \"Mom's birthday\", \"Stats midterm\""},
        "person": {"type": "string", "description": "who it's about, if anyone (e.g. \"Mom\"), else empty"},
        "date": {"type": "string", "description": "YYYY-MM-DD of the next occurrence, or empty if none"},
        "time": {"type": "string", "description": "HH:MM 24h if the user gave a time, else empty"},
        "repeat": {"type": "string", "enum": REPEATS},
    },
    "required": ["category", "title", "person", "date", "time", "repeat"],
    "additionalProperties": False,
}


def _parse_with_claude(text: str, today: date) -> dict | None:
    if not config.ANTHROPIC_API_KEY:
        return None
    import anthropic
    from .integrations import _claude_client

    cats = "; ".join(f"{k}: {v['label']}, usually repeats {v['repeat']}" for k, v in CATEGORIES.items())
    try:
        resp = _claude_client().beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=("You turn one short note into a calendar event for a reminder app. "
                    f"Today is {today:%A %Y-%m-%d}. Categories: {cats}. "
                    "Pick the closest category ('task' if none fits). For dates without a year use "
                    "the next occurrence on or after today. Use the category's usual repeat unless "
                    "the note says otherwise."),
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.APIError as e:
        log.warning("Claude could not parse the event, using rules: %s", e)
        return None
    if resp.stop_reason == "refusal":
        return None
    raw = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _parse_with_rules(text: str, today: date) -> dict:
    low = text.lower()
    category = next((k for k, v in CATEGORIES.items() if any(w in low for w in v["keywords"])), "task")
    repeat = CATEGORIES[category]["repeat"]
    d = None
    try:
        from dateutil import parser as dparser
        sentinel = datetime(1900, 1, 1)
        parsed = dparser.parse(text, fuzzy=True, default=sentinel)
        if re.search(r"\btoday\b", low):
            d = today
        elif parsed != sentinel:
            got_year = parsed.year != 1900
            d = parsed.date().replace(year=parsed.year if got_year else today.year)
            if parsed.month == 1 and not re.search(r"\bjan", low):  # only a day was given ("the 1st")
                d = d.replace(month=today.month)
            if d < today and not got_year:
                d = _add_months(d, 1) if repeat == "monthly" else d.replace(year=d.year + 1)
    except (ValueError, OverflowError, ImportError):
        pass
    m = re.search(r"\b([A-Z][a-z]+|mom|dad|mum)'s\b", text)
    person = m.group(1) if m else ""
    title = re.sub(r"\b(on|by|due|at)\b.*$", "", text, flags=re.I)
    title = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?\b.*$",
                   "", title, flags=re.I).strip(" ,.") or text.strip()
    return {"category": category, "title": title[:80], "person": person,
            "date": d.isoformat() if d else "", "time": "", "repeat": repeat}


def add(chat_id: str, text: str, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    parsed = _parse_with_claude(text, now.date()) or _parse_with_rules(text, now.date())
    cat = parsed["category"] if parsed["category"] in CATEGORIES else "task"
    ev = {
        "id": uuid.uuid4().hex[:4],
        "chat_id": str(chat_id),
        "title": parsed["title"] or text.strip(),
        "category": cat,
        "person": parsed.get("person") or "",
        "date": parsed.get("date") or None,
        "time": parsed.get("time") or None,
        "repeat": parsed.get("repeat") if parsed.get("repeat") in REPEATS else CATEGORIES[cat]["repeat"],
        "source_text": text,
        "created_at": now.isoformat(timespec="seconds"),
        "fired": [],
    }
    if ev["repeat"] != "daily" and not ev["date"]:
        ev["date"] = now.date().isoformat()  # no date given: treat as today
    events = load()
    events.append(ev)
    save(events)
    return ev


# ---------------------------------------------------------------- scheduling
def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, monthrange(y, m)[1]))


def next_occurrence(ev: dict, today: date) -> date | None:
    """The event date we're reminding about: the next one on or after today."""
    if ev["repeat"] == "daily":
        return today
    if not ev.get("date"):
        return None
    d = date.fromisoformat(ev["date"])
    if ev["repeat"] == "yearly":
        try:
            d = d.replace(year=today.year)
        except ValueError:  # Feb 29
            d = date(today.year, 3, 1)
        return d if d >= today else d.replace(year=today.year + 1)
    if ev["repeat"] == "monthly":
        while d < today:
            d = _add_months(d, 1)
        return d
    if ev["repeat"] == "weekly":
        return d + timedelta(days=((today - d).days + 6) // 7 * 7) if d < today else d
    return d if d >= today else None


def reminders(ev: dict, today: date) -> list[tuple[str, datetime, int]]:
    """(key, when, days_left) for each call planned for the current/next occurrence."""
    cat = CATEGORIES.get(ev["category"], CATEGORIES["task"])
    out = []
    for back in (0, 1):  # also look at yesterday's occurrence so a reminder at 23:00 isn't lost
        occ = next_occurrence(ev, today - timedelta(days=back))
        if not occ:
            continue
        times = [ev["time"]] if ev.get("time") and cat["repeat"] == "none" else cat["at"]
        for days in cat["lead_days"]:
            for t in times:
                hh, mm = (int(x) for x in t.split(":"))
                when = datetime.combine(occ - timedelta(days=days), datetime.min.time()).replace(hour=hh, minute=mm)
                out.append((f"{occ.isoformat()}@{days}d@{t}", when, days))
    return sorted(set(out), key=lambda r: r[1])


def due(now: datetime | None = None) -> list[tuple[dict, str, int]]:
    """Reminders whose time has come (and not too long ago), not yet fired."""
    now = now or datetime.now()
    found = []
    for ev in load():
        for key, when, days in reminders(ev, now.date()):
            if when <= now <= when + GRACE and key not in ev.get("fired", []):
                found.append((ev, key, days))
    return found


def mark_fired(event_id: str, key: str) -> None:
    events = load()
    for e in events:
        if e["id"] == event_id and key not in e.setdefault("fired", []):
            e["fired"].append(key)
            e["fired"] = e["fired"][-50:]
    save(events)


def next_call(ev: dict, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now()
    upcoming = [w for k, w, _ in reminders(ev, now.date()) if w > now and k not in ev.get("fired", [])]
    if not upcoming:  # look ahead (yearly / monthly events)
        for days_ahead in (1, 7, 31, 366):
            upcoming = [w for k, w, _ in reminders(ev, now.date() + timedelta(days=days_ahead)) if w > now]
            if upcoming:
                break
    return min(upcoming) if upcoming else None


# ---------------------------------------------------------------- turning a reminder into a task
def task_for(ev: dict, days_left: int) -> tuple[str, str]:
    """(task title, deadline text) for the call."""
    cat = CATEGORIES.get(ev["category"], CATEGORIES["task"])
    prefix = cat["task"].split("{title}")[0].strip().lower()
    t = ev["title"]
    if prefix and t.lower().split()[:1] == prefix.split()[:1]:  # "take" + "Take vitamins" -> "take vitamins"
        title = t[0].lower() + t[1:]
    else:
        title = cat["task"].format(title=t, person=ev.get("person") or "them").strip()
    occ = next_occurrence(ev, date.today()) if ev["repeat"] != "daily" else None
    if not occ or ev["repeat"] == "daily":
        when = "today"
    elif days_left == 0:
        when = "today"
    elif days_left == 1:
        when = f"tomorrow ({occ:%b} {occ.day})"
    else:
        when = f"in {days_left} days ({occ:%b} {occ.day})"
    return title, when


def describe(ev: dict) -> str:
    cat = CATEGORIES.get(ev["category"], CATEGORIES["task"])
    rep = {"yearly": "every year", "monthly": "every month", "weekly": "every week",
           "daily": "every day", "none": "once"}[ev["repeat"]]
    d = f" on {date.fromisoformat(ev['date']):%b} {date.fromisoformat(ev['date']).day}" if ev.get("date") and ev["repeat"] != "daily" else ""
    lead = ", ".join("on the day" if x == 0 else f"{x}d before" for x in cat["lead_days"])
    return (f"{cat['emoji']} {ev['title']} · {cat['label']} · {rep}{d} · "
            f"calls: {lead} at {', '.join([ev['time']] if ev.get('time') and cat['repeat'] == 'none' else cat['at'])}")
