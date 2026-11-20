"""Read intent from free text (typed or transcribed from voice).

Shared by the Telegram bot and the Firedrill bridge, so both follow the same rules.
"""
from __future__ import annotations

import re

from .nudges import clean_task

START_WORDS = re.compile(
    r"\b(started|starting|start now|on it|doing it|opened|opening|ok(ay)? i'?ll|let'?s go|i'?m in|fine"
    r"|i'?ll start|i'?ll do it|let me start|alright)\b",
    re.I,
)
NEGATION = re.compile(
    r"\b(not|no|nah|nope|never|don'?t|won'?t|can'?t|isn'?t|ain'?t|refuse|stop)\b", re.I)
DEADLINE = re.compile(r"\b(?:by|due|before)\s+(.+)$", re.I)


def is_start(text: str) -> bool:
    """'ok fine opening it' is a start; 'not opening it' is not (found by a Firedrill drill)."""
    return bool(START_WORDS.search(text)) and not NEGATION.search(text)


def parse_task(text: str) -> tuple[str, str | None]:
    """'I need to finish my pitch by 4:30.' -> ('your pitch', '4:30')."""
    text = text.strip().rstrip(".!?")
    m = DEADLINE.search(text)
    deadline = m.group(1).strip(" .") if m else None
    return clean_task(text[: m.start()] if m else text)[:200], deadline
