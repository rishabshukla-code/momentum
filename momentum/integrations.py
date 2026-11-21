"""Partner integrations. Each one degrades gracefully to a local fallback.

  write_nudge()     Arcee (or any OpenAI-compatible LLM) writes the message
  classify_excuse() Superlinked task-specific model classifies a free-text reply
  remember/recall   Cognee memory graph of what works for this person
  track()           Amplitude events for every agent decision and outcome
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import time
import wave

import httpx
from amplitude import BaseEvent

from . import config
from .analytics import client as amplitude_client
from .nudges import NUDGE_TYPES, fallback_text

log = logging.getLogger("momentum")


# ---------------------------------------------------------------- LLM writer
_claude = None

CLAUDE_SYSTEM = (
    "You are Momentum: a calm, warm presence that helps one person start their work, like a kind, "
    "steady friend who knows them well. Your words will be spoken aloud, slowly and softly. "
    "Write a single nudge: at most 18 words, plain text, starting with the emoji you are given. "
    "Follow the requested nudge style exactly; it is the whole point of the message. "
    "Voice: unhurried and gentle. Short, simple sentences. Use commas for natural pauses. Never use "
    "exclamation marks, capital letters for emphasis, or words like 'now!', 'hurry' or 'immediately'. "
    "Firm styles stay calm too: say the consequence plainly and kindly, the way a trusted friend "
    "would, never like a coach shouting. Never insult, shame, mock or threaten. "
    "Context you are given is for choosing your tone, not for repeating back: never mention the "
    "time of day, and never restate or guess about their earlier excuse or how they feel "
    "(if they were tired, keep the ask small and gentle instead of saying so). Mention the "
    "deadline only if one is given, and never suggest it can be ignored. Only use facts you are "
    "given: never invent people, teams or details. No hashtags, quotes, lists or sign-offs. "
    "Reply with the nudge only."
)


def _claude_client():
    global _claude
    if _claude is None:
        import anthropic
        _claude = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=20.0, max_retries=1)
    return _claude


def write_with_claude(arm, facts: list[str]) -> str:
    """One short nudge from Claude. Returns '' on refusal or error (caller falls back to a template)."""
    import anthropic

    t = NUDGE_TYPES[arm]
    prompt = (f"Nudge style: {t['label']}: {t['style']}.\nStart with this emoji: {t['emoji']}\n"
              + "\n".join(facts))
    try:
        resp = _claude_client().beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            system=CLAUDE_SYSTEM,
            output_config={"effort": "low"},  # a one-line nudge needs little thinking
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if a safety classifier declines, the API retries on a fallback model
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        log.warning("Claude: the API key was rejected")
        return ""
    except anthropic.RateLimitError:
        log.warning("Claude: rate limited, using a template")
        return ""
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s: %s", e.status_code, e.message)
        return ""
    except anthropic.APIConnectionError:
        log.warning("Claude: network error, using a template")
        return ""
    if resp.stop_reason == "refusal":
        return ""
    text = "".join(b.text for b in resp.content if b.type == "text").strip().strip('"')
    return text.splitlines()[0].strip() if text else ""


def write_nudge(arm, task, deadline, context, streak, excuse=None, memories=None) -> tuple[str, str]:
    """Return (text, source) where source is 'claude', 'llm' (Arcee) or 'template'."""
    use_claude = config.NUDGE_WRITER != "template" and bool(config.ANTHROPIC_API_KEY)
    use_arcee = (config.NUDGE_WRITER != "template"
                 and bool(config.LLM_BASE_URL and config.LLM_API_KEY and config.LLM_MODEL))
    if use_claude:
        facts = [f"Task: {task}", f"Deadline: {deadline or 'none given'}", f"Time of day: {context}"]
        if streak >= 2:
            facts.append(f"They started on time {streak} times in a row recently.")
        if excuse:
            facts.append(f"Last time they said no because they were {excuse}.")
        text = write_with_claude(arm, facts)
        if text:
            emoji = NUDGE_TYPES[arm]["emoji"]
            return (text if text.startswith(emoji) else f"{emoji} {text}"), "claude"
        return fallback_text(arm, task, deadline, streak), "template"
    if not use_arcee:
        return fallback_text(arm, task, deadline, streak), "template"
    t = NUDGE_TYPES[arm]
    facts = [f"Task: {task}", f"Deadline: {deadline or 'none given'}", f"Time of day: {context}"]
    if streak:
        facts.append(f"They started on time {streak} times in a row recently.")
    if excuse:
        facts.append(f"Their last excuse was: {excuse}.")
    if memories:
        facts.append("What you know about them: " + "; ".join(memories[:3]))
    prompt = (
        "You are Momentum, a warm, familiar presence that helps someone start their work, "
        "like someone at home who knows them well. Write ONE short nudge (max 20 words). "
        f"Style: {t['style']}. Start with the emoji {t['emoji']}. No hashtags, no quotes.\n"
        + "\n".join(facts)
    )
    try:
        text = chat(prompt)
        if not text:
            raise ValueError("empty reply")
        return (text if text.startswith(t["emoji"]) else f"{t['emoji']} {text}"), "llm"
    except Exception as e:  # never let the LLM break the loop
        log.warning("LLM failed, using template: %s", e)
        return fallback_text(arm, task, deadline, streak), "template"


def chat(prompt: str, timeout: float = 20) -> str:
    """One chat completion against the configured OpenAI-compatible endpoint (Arcee)."""
    thinking = "thinking" in config.LLM_MODEL.lower()
    r = httpx.post(
        config.LLM_BASE_URL.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        json={"model": config.LLM_MODEL, "temperature": 0.9,
              # thinking models spend tokens reasoning before they answer
              "max_tokens": 1500 if thinking else 80,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60 if thinking else timeout,
    )
    r.raise_for_status()
    text = (r.json()["choices"][0]["message"].get("content") or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return text.strip().strip('"').splitlines()[0].strip() if text else ""


# ------------------------------------------------------ AssemblyAI speech-to-text
def transcribe(audio: bytes) -> str:
    """Turn a short recorded answer into text with AssemblyAI. Returns '' on failure."""
    if not config.ASSEMBLYAI_API_KEY or not audio:
        return ""
    h = {"authorization": config.ASSEMBLYAI_API_KEY}
    try:
        up = httpx.post("https://api.assemblyai.com/v2/upload", headers=h, content=audio, timeout=30)
        up.raise_for_status()
        job = httpx.post("https://api.assemblyai.com/v2/transcript", headers=h,
                         json={"audio_url": up.json()["upload_url"]}, timeout=30)
        job.raise_for_status()
        tid = job.json()["id"]
        for _ in range(40):  # short clips finish in a few seconds
            r = httpx.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=h, timeout=15).json()
            if r.get("status") == "completed":
                return (r.get("text") or "").strip()
            if r.get("status") == "error":
                log.warning("AssemblyAI error: %s", r.get("error"))
                return ""
            time.sleep(0.5)
    except Exception as e:
        log.warning("AssemblyAI failed: %s", e)
    return ""


TTS_VOICE = os.getenv("ASSEMBLYAI_TTS_VOICE", "aai-audrey")  # calm, even, steady (Kyla is fast-paced)
_tts_cache: dict[str, bytes] = {}


def speak(text: str) -> bytes:
    """Natural voice for Momentum Phone: AssemblyAI streaming TTS -> WAV bytes ('' on failure).

    Same protocol as the assemblyai-livekit-tts plugin: open the socket (Begin), send
    Generate + Terminate, collect base64 PCM Audio frames until Termination.
    """
    if not config.ASSEMBLYAI_API_KEY or not text:
        return b""
    if text in _tts_cache:
        return _tts_cache[text]
    from urllib.parse import urlencode

    from websockets.sync.client import connect

    rate = 24000
    url = "wss://tts.us.assemblyai.com/v1/ws/?" + urlencode({
        "voice_id": TTS_VOICE, "language": "english", "model": "assemblyai-tts-1",
        "sample_rate": rate, "encoding": "pcm_s16le", "word_boundaries": "false"})
    pcm = bytearray()
    try:
        with connect(url, additional_headers={"Authorization": config.ASSEMBLYAI_API_KEY},
                     open_timeout=10, close_timeout=2) as ws:
            first = json.loads(ws.recv(timeout=10))
            if first.get("type") == "Error":
                raise RuntimeError(first)
            ws.send(json.dumps({"type": "Generate", "text": text}))
            ws.send(json.dumps({"type": "Terminate"}))
            while True:
                msg = json.loads(ws.recv(timeout=20))
                if msg.get("type") == "Audio":
                    pcm += base64.b64decode(msg["audio"])
                elif msg.get("type") in ("Termination", "Error"):
                    break
    except Exception as e:
        log.warning("AssemblyAI TTS failed: %s", e)
        return b""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))
    _tts_cache[text] = buf.getvalue()
    return _tts_cache[text]


# ------------------------------------------------------ Superlinked excuses
EXCUSES = ["tired", "overwhelmed", "busy", "bored", "unclear"]
KEYWORDS = {
    "tired": ["tired", "sleepy", "exhausted", "no energy", "drained"],
    "overwhelmed": ["too much", "overwhelm", "stressed", "anxious", "don't know where"],
    "busy": ["busy", "meeting", "class", "later", "out", "driving"],
    "bored": ["boring", "bored", "don't want", "dont want", "meh"],
    "unclear": ["confused", "not sure", "stuck", "what do i", "how do i"],
}
# Which nudge types fit each excuse. Strong enough to beat random exploration
# (a Firedrill drill showed weak boosts let "tired" get a pressure nudge),
# while the brain still chooses between the fitting types.
EXCUSE_BOOST = {
    "tired": {"tiny_step": 0.6, "reward": 0.45, "five_minute": 0.5, "music": 0.4},
    "overwhelmed": {"tiny_step": 0.7, "five_minute": 0.5, "first_line": 0.5, "body_double": 0.4},
    # firm nudges only for "busy" / "bored"; never after "tired" or "overwhelmed" (pressure backfires)
    "busy": {"tiny_step": 0.4, "consequence": 0.3, "five_minute": 0.5, "cost_of_delay": 0.35},
    "bored": {"reward": 0.5, "music": 0.5, "tough_love": 0.35, "first_line": 0.3},
    "unclear": {"tiny_step": 0.6, "first_line": 0.6},
}


def classify_excuse(text: str) -> tuple[str, str]:
    """Return (label, source). Uses Superlinked if configured, else keywords."""
    if config.SUPERLINKED_URL:
        try:
            # Placeholder request shape: adjust to the Superlinked endpoint from their cookbook.
            r = httpx.post(
                config.SUPERLINKED_URL,
                headers={"Authorization": f"Bearer {config.SUPERLINKED_API_KEY}"},
                json={"text": text, "labels": EXCUSES},
                timeout=10,
            )
            r.raise_for_status()
            label = r.json().get("label")
            if label in EXCUSES:
                return label, "superlinked"
        except Exception as e:
            log.warning("Superlinked failed, using keywords: %s", e)
    low = text.lower()
    for label, words in KEYWORDS.items():
        if any(w in low for w in words):
            return label, "keywords"
    return "busy", "keywords"


# ---------------------------------------------------------- Cognee memory
def _run(coro):
    try:
        return asyncio.run(coro)
    except Exception as e:
        log.warning("Cognee call failed: %s", e)
        return None


def remember(chat_id: str, fact: str) -> None:
    if not config.COGNEE_ENABLED:
        return
    try:
        import cognee
    except ImportError:
        return
    _run(cognee.add(fact, dataset_name=f"user_{chat_id}"))


def build_memory(chat_id: str) -> None:
    if not config.COGNEE_ENABLED:
        return
    try:
        import cognee
    except ImportError:
        return
    _run(cognee.cognify(datasets=[f"user_{chat_id}"]))


def recall(chat_id: str, query: str) -> list[str]:
    if not config.COGNEE_ENABLED:
        return []
    try:
        import cognee
    except ImportError:
        return []
    res = _run(cognee.search(query_text=query, datasets=[f"user_{chat_id}"]))
    return [str(r) for r in (res or [])][:3]


# ---------------------------------------------------------- Amplitude
def track(chat_id: str, event: str, props: dict) -> None:
    if amplitude_client is None:
        return
    try:
        amplitude_client.track(BaseEvent(
            event_type=event, user_id=f"tg_{chat_id}", event_properties=props,
        ))
    except Exception as e:
        log.warning("Amplitude failed: %s", e)
