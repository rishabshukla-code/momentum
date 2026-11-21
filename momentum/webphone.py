"""Momentum Phone: a browser page that simulates a real phone call for a nudge.

The page (phone.html) rings, you Accept or Decline; if nobody answers it goes to
voicemail. On Accept, the nudge is spoken aloud, your spoken answer is recorded and
transcribed with AssemblyAI, and the same intent rules as everywhere else decide:
started, or not now (with an excuse). Only the outcome and excuse label are stored.

Routes (served by server.py, protected by ?k=TRIGGER_TOKEN):
  GET  /phone               the call page
  GET  /phone/api/next      a waiting call, if any
  POST /phone/api/answer    spoken audio (or {"text": ...}) for the current call
  POST /phone/api/end       declined / missed / hung_up
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import config, store
from .voice import spoken

log = logging.getLogger("momentum")
router = APIRouter(prefix="/phone")
PAGE = Path(__file__).with_name("phone.html")
SERVED: set[int] = set()  # calls already delivered to the page


def _check(k: str, request: Request | None = None) -> None:
    # On this laptop (not through the public tunnel, which adds cf-connecting-ip) no token is needed.
    if request is not None and request.client and request.client.host in ("127.0.0.1", "::1") \
            and "cf-connecting-ip" not in request.headers:
        return
    if not k or k != config.TRIGGER_TOKEN:
        raise HTTPException(403, "forbidden")


def _name(chat_id: str) -> str:
    import re
    u = store.get_user(chat_id)
    name = re.sub(r"\s*\(.*?\)", "", (u and u["name"]) or "").strip()  # "Maya (demo, simulated)" -> "Maya"
    return name or "there"


def _nudge_label(arm: str) -> str:
    from .nudges import NUDGE_TYPES
    t = NUDGE_TYPES.get(arm)
    return f"{t['emoji']} {t['label']}" if t else arm


def _mirror(chat_id: str, text: str) -> None:
    from . import telegram
    try:
        telegram.send(chat_id, text)
    except Exception as e:
        log.warning("could not mirror call result to Telegram: %s", e)


@router.get("", response_class=HTMLResponse)
def page(request: Request, k: str = ""):
    _check(k, request)
    return PAGE.read_text(encoding="utf-8")


@router.get("/api/next")
def next_call(request: Request, k: str = ""):
    _check(k, request)
    recent = store.recent_nudges(10)
    for i, r in enumerate(recent):
        if r["message_id"] == "web" and r["outcome"] is None and r["id"] not in SERVED:
            SERVED.add(r["id"])
            earlier = next((x for x in recent[i + 1:] if x["chat_id"] == r["chat_id"]), None)
            hello = ("it's Momentum again, like I promised."
                     if earlier and earlier["outcome"] == "deferred" else "it's Momentum.")
            return {"call": {
                "id": str(r["id"]),
                "greeting": f"Hey {_name(r['chat_id'])}, {hello} {spoken(r['text'])} Have you started?",
                "reason": r["reason"],
                "nudge": _nudge_label(r["arm"]),
                "voice": bool(config.ASSEMBLYAI_API_KEY),
            }}
    return {"call": None}


@router.post("/api/tts")
async def tts(request: Request, k: str = ""):
    """Natural voice for the call page (AssemblyAI TTS). 204 if unavailable -> browser voice."""
    _check(k, request)
    from fastapi.responses import Response as Raw
    from fastapi.concurrency import run_in_threadpool
    from .integrations import speak

    text = str((await request.json()).get("text", ""))[:600]
    wav = await run_in_threadpool(speak, text)
    return Raw(wav, media_type="audio/wav") if wav else Raw(status_code=204)


@router.post("/api/answer")
async def answer(request: Request, id: str, k: str = ""):
    _check(k, request)
    from .agent import record_outcome
    from .integrations import classify_excuse, transcribe
    from .intent import is_start, parse_defer
    from .replies import minutes_text, pick

    nudge_id = int(id)
    row = store.get_nudge(nudge_id)
    if not row:
        raise HTTPException(404, "no such call")
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        heard = str((await request.json()).get("text", "")).strip()
    else:
        heard = transcribe(await request.body())

    later = parse_defer(heard) if heard else None
    if later:  # "I'll do it in a while": not a yes, not a no; call back when promised
        record_outcome(nudge_id, "deferred")
        store.set_excuse(nudge_id, f"later:{later}")
        say = pick("deferred", mins=minutes_text(later))
        note = f"⏳ later (calling back in {minutes_text(later)})"
    elif heard and is_start(heard):
        record_outcome(nudge_id, "started")
        say, note = pick("started"), "✅ started"
    else:
        record_outcome(nudge_id, "snoozed")
        excuse, _ = classify_excuse(heard or "busy")
        store.set_excuse(nudge_id, excuse)
        say = pick("snoozed", excuse=excuse)
        note = f"😴 not now ({excuse})"
    _mirror(row["chat_id"], f"📞 On the call you said: “{heard or '…'}” → {note}")
    return {"heard": heard, "say": say, "note": note}


@router.post("/api/end")
async def end(request: Request, k: str = ""):
    _check(k, request)
    from .agent import record_outcome

    body = await request.json()
    nudge_id, how = int(body.get("id")), body.get("how")
    row = store.get_nudge(nudge_id)
    if not row:
        return {"note": ""}
    if how == "missed":
        record_outcome(nudge_id, "ignored")
        vm = (f"Hey {_name(row['chat_id'])}, it's Momentum. {spoken(row['text'])} "
              "Call me back when you're ready.")
        _mirror(row["chat_id"], "📞 Missed call from Momentum. Left a voicemail.")
        return {"voicemail": vm, "note": "missed"}
    if row["outcome"] is None:  # declined, or hung up before answering
        record_outcome(nudge_id, "snoozed")
        store.set_excuse(nudge_id, "busy")
        _mirror(row["chat_id"], "📞 You declined Momentum's call → 😴 not now (busy)")
    return {"note": "Declined. I'll try again later."}
