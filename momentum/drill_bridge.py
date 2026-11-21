"""Firedrill bridge (jsonl-process.v1): lets synthetic users talk to Momentum.

Reads one JSON request per line on stdin:
    {"id": ..., "session": ..., "kind": ..., "input": ...}
and writes one line per request on stdout:
    {"id": ..., "output": {...}}   or   {"id": ..., "error": "..."}
Logs go to stderr only.

Conversation contract (one drill = one session = one synthetic user):
  1st turn  the user says what they need to work on (optionally "... by <deadline>").
            Momentum replies with its first nudge.
  later     the user replies. "started" / "on it" / "opening it" counts as a start;
            anything else counts as "not now", and the text is classified as an excuse.
            Momentum records the outcome and, if needed, sends a different nudge.
  It sends at most MAX_NUDGES_PER_BLOCK nudges, and stops as soon as the user starts.

Every reply includes the audit trail: nudge type, why it was chosen, and the
excuse label, so Firedrill can check what the agent did, not only what it said.

State: a fresh SQLite file per process (fresh-process reset). Each session is
kept separate by its session id.

Run:  python -m momentum.drill_bridge
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

_db = os.path.join(tempfile.gettempdir(), f"momentum_drill_{os.getpid()}.db")
if os.path.exists(_db):
    os.remove(_db)
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("NUDGE_WRITER", "template")  # drills stay free and repeatable

from . import brain, config, store  # noqa: E402  (env must be set first)
from .agent import record_outcome  # noqa: E402
from .integrations import EXCUSE_BOOST, classify_excuse, write_nudge  # noqa: E402
from .intent import is_start, parse_task  # noqa: E402


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _text_of(inp) -> str:
    if isinstance(inp, str):
        return inp
    if isinstance(inp, dict):
        for k in ("message", "text", "content", "input", "prompt"):
            if isinstance(inp.get(k), str):
                return inp[k]
    return json.dumps(inp)


def _nudge(sid: str) -> dict:
    """Pick, write and log a nudge without Telegram. Returns the audit record."""
    from datetime import datetime

    task = store.active_task(sid)
    last = store.last_nudge(sid)
    boost = dict(EXCUSE_BOOST.get(last["excuse"], {})) if last and last["excuse"] else {}
    streak = store.streak(sid)
    if streak < 2:
        boost["streak"] = -1.0
    d = brain.choose(store.history(sid), datetime.now(), boost=boost,
                     excuse=last["excuse"] if last else None)
    text, source = write_nudge(d.arm, task["title"], task["deadline"], d.context, streak,
                               last and last["excuse"])
    nid = store.log_nudge(sid, task["id"], d.arm, d.context, text, d.reason)
    return {"nudge_id": nid, "nudge_type": d.arm, "reason": d.reason, "writer": source,
            "text": text}


def handle(sid: str, text: str) -> dict:
    store.upsert_user(sid, "drill")
    task = store.active_task(sid)
    last = store.last_nudge(sid)

    # First turn: set the task and send the first nudge.
    if not task and not last:
        title, deadline = parse_task(text)
        store.add_task(sid, title, deadline)
        n = _nudge(sid)
        return {"reply": n["text"] + "\n(Reply 'started', or tell me what's in the way.)",
                "action": "nudge_sent", "audit": n}

    if not task:
        if last and last["outcome"] == "started":
            return {"reply": "You already got going. I'll stay quiet. ☕", "action": "none"}
        return {"reply": "No pressure. I'm here whenever you're ready. ☕", "action": "none"}

    pending = last if last and last["outcome"] is None else None
    if pending and is_start(text):
        record_outcome(pending["id"], "started")
        return {"reply": "Love that. Go go go. 🔥", "action": "stopped_nudging",
                "audit": {"nudge_id": pending["id"], "outcome": "started"}}

    excuse = None
    if pending:
        excuse, src = classify_excuse(text)
        record_outcome(pending["id"], "snoozed")
        store.set_excuse(pending["id"], excuse)
        _log(f"[{sid}] excuse={excuse} via {src}")

    if store.nudges_for_task(task["id"]) >= config.MAX_NUDGES_PER_BLOCK:
        store.finish_task(sid)
        return {"reply": "Okay, no more nudges for now. I'll check in later. Be kind to yourself. ☕",
                "action": "gave_up_for_now", "audit": {"excuse": excuse,
                                                       "max_nudges": config.MAX_NUDGES_PER_BLOCK}}
    n = _nudge(sid)
    n["previous_excuse"] = excuse
    return {"reply": n["text"] + "\n(Reply 'started', or tell me what's in the way.)",
            "action": "nudge_sent", "audit": n}


def as_text(out: dict) -> str:
    """Reply text for the simulated user, plus one [audit] line the evaluator can score."""
    a = out.get("audit") or {}
    bits = [f"action={out.get('action')}"]
    for k in ("nudge_type", "reason", "previous_excuse", "outcome"):
        if a.get(k):
            bits.append(f"{k}={a[k]}")
    return f"{out['reply']}\n[audit] " + " | ".join(bits)


def main() -> None:
    store.init_db()
    _log(f"momentum drill bridge ready (db={_db})")
    print("READY", flush=True)  # Firedrill stdout readiness line
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("id")
            sid = str(req.get("session") or "default")
            out = handle(sid, _text_of(req.get("input")))
            resp = {"id": rid, "output": as_text(out)}
        except Exception as e:  # report, never crash the bridge
            _log(f"error: {e!r}")
            resp = {"id": rid, "error": str(e)}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
