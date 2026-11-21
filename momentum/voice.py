"""Phone-call delivery: Momentum calls you, says the nudge, and listens to your answer.

  "Hey Rishab. Two minutes on your pitch, that's it. Did you start?"
  You: "thanks, I'll start now"        -> started, nudging stops
  You: "not now, I'm still at work"    -> not now, excuse "busy", next nudge adapts

Twilio places the call and does live speech-to-text (<Gather input="speech">).
Its webhooks (/voice/twiml, /voice/reply) are served by server.py and must be
reachable at PUBLIC_BASE_URL. Every webhook is checked against Twilio's signature.
Only the outcome and excuse label are stored, never the audio or the transcript.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
from pathlib import Path
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Request, Response

from . import config, store

log = logging.getLogger("momentum")
PREFS = Path(__file__).resolve().parent.parent / "call_prefs.json"
router = APIRouter(prefix="/voice")


# ------------------------------------------------------------- preferences
def ready() -> bool:
    return all([config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN, config.TWILIO_FROM_NUMBER,
                config.CALL_TO_NUMBER, config.PUBLIC_BASE_URL])


def _prefs() -> dict:
    try:
        return json.loads(PREFS.read_text())
    except (OSError, ValueError):
        return {}


def call_enabled(chat_id: str) -> bool:
    return call_mode(chat_id) == "twilio"


def call_mode(chat_id: str) -> str | None:
    """None (Telegram), "twilio" (real phone call) or "web" (Momentum Phone page)."""
    v = _prefs().get(str(chat_id))
    return "twilio" if v is True else (v or None)


def set_call(chat_id: str, on) -> None:
    p = _prefs()
    p[str(chat_id)] = on
    PREFS.write_text(json.dumps(p))


# ------------------------------------------------------------- outbound call
def spoken(text: str) -> str:
    """Drop emoji and symbols so the voice reads the nudge cleanly."""
    return re.sub(r"[^\w\s.,!?'’:;-]", "", text).strip()


def place_call(nudge_id: int) -> str:
    r = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Calls.json",
        auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
        data={"To": config.CALL_TO_NUMBER, "From": config.TWILIO_FROM_NUMBER,
              "Url": f"{config.PUBLIC_BASE_URL}/voice/twiml?nudge_id={nudge_id}", "Method": "POST"},
        timeout=15,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Twilio call failed: {r.status_code} {r.text[:200]}")
    return r.json()["sid"]


# ------------------------------------------------------------- webhooks
def _valid(request: Request, form: dict) -> bool:
    """Twilio signs each webhook with the auth token (HMAC-SHA1 of URL + sorted params)."""
    if not config.TWILIO_AUTH_TOKEN:
        return False
    url = config.PUBLIC_BASE_URL + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    payload = url + "".join(k + form[k] for k in sorted(form))
    digest = hmac.new(config.TWILIO_AUTH_TOKEN.encode(), payload.encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, request.headers.get("X-Twilio-Signature", ""))


def _twiml(body: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>',
                    media_type="application/xml")


def _say(text: str) -> str:
    return f'<Say voice="{escape(config.CALL_VOICE)}">{escape(text)}</Say>'


@router.post("/twiml")
async def twiml(request: Request, nudge_id: int):
    form = {k: str(v) for k, v in (await request.form()).items()}
    if not _valid(request, form):
        return Response("forbidden", status_code=403)
    row = store.get_nudge(nudge_id)
    if not row:
        return _twiml(_say("Sorry, I lost my train of thought. Talk soon.") + "<Hangup/>")
    user = store.get_user(row["chat_id"])
    name = (user and user["name"]) or "there"
    action = escape(f"{config.PUBLIC_BASE_URL}/voice/reply?nudge_id={nudge_id}")
    return _twiml(
        f'<Gather input="speech" action="{action}" method="POST" speechTimeout="auto" language="en-US">'
        + _say(f"Hey {name}, it's Momentum. {spoken(row['text'])} Have you started?")
        + "</Gather>"
        + _say("No worries. I'll check back later. Bye!")
    )


@router.post("/reply")
async def reply(request: Request, nudge_id: int):
    from .agent import record_outcome  # avoid a circular import
    from .integrations import classify_excuse
    from .intent import is_start, parse_defer
    from .replies import minutes_text, pick
    from . import telegram

    form = {k: str(v) for k, v in (await request.form()).items()}
    if not _valid(request, form):
        return Response("forbidden", status_code=403)
    heard = form.get("SpeechResult", "").strip()
    row = store.get_nudge(nudge_id)
    if not row:
        return _twiml(_say("Got it. Bye!") + "<Hangup/>")

    later = parse_defer(heard) if heard else None
    if later:
        record_outcome(nudge_id, "deferred")
        store.set_excuse(nudge_id, f"later:{later}")
        answer, note = pick("deferred", mins=minutes_text(later)), f"⏳ later ({minutes_text(later)})"
    elif heard and is_start(heard):
        record_outcome(nudge_id, "started")
        answer, note = pick("started"), "✅ started"
    else:
        record_outcome(nudge_id, "snoozed")
        excuse, _ = classify_excuse(heard or "busy")
        store.set_excuse(nudge_id, excuse)
        answer, note = pick("snoozed", excuse=excuse), f"😴 not now ({excuse})"
    try:  # show the result in the chat too, so it's visible next to the dashboard
        telegram.send(row["chat_id"], f"📞 You said: “{heard or '…'}” → {note}")
    except Exception as e:
        log.warning("could not post call result to Telegram: %s", e)
    return _twiml(_say(answer) + "<Hangup/>")
