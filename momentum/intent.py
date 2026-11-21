"""Read intent from free text (typed or transcribed from voice).

Shared by the Telegram bot and the Firedrill bridge, so both follow the same rules.
"""
from __future__ import annotations

import re

from .nudges import clean_task

START_WORDS = re.compile(
    r"\b(started|starting|start now|on it|doing it|opened|opening|ok(ay)? i'?ll|let'?s go|i'?m in|fine"
    r"|i'?ll start|i'?ll do it|let me start|alright|taking (?:it|them)|doing (?:it|that)|will do"
    r"|yes|yep|yeah|sure|right now|now)\b",
    re.I,
)
NEGATION = re.compile(
    r"\b(not|no|nah|nope|never|don'?t|won'?t|can'?t|isn'?t|ain'?t|refuse|stop)\b", re.I)
DEADLINE = re.compile(r"\b(?:by|due|before)\s+(.+)$", re.I)


_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "couple": 2, "a couple": 2, "a couple of": 2,
        "three": 3, "few": 5, "a few": 5, "five": 5, "ten": 10, "fifteen": 15, "twenty": 20,
        "thirty": 30, "half an": 30, "half": 30}
DEFER_EXACT = re.compile(
    r"\b(?:in|give me|after|wait)\s+(?:another\s+)?"
    r"(\d+|a couple of|a couple|couple|a few|few|half an|an|a|one|two|three|five|ten|fifteen|twenty|thirty)"
    r"\s*(min(?:ute)?s?|hours?|hrs?)\b", re.I)
DEFER_VAGUE = re.compile(
    r"\b(in a (?:bit|while|sec|second|moment|minute)|later|after (?:this|that|lunch|dinner|class|work|my \w+)"
    r"|soon|give me (?:a )?(?:sec|second|minute|moment|bit)|not yet|in a little while|shortly)\b", re.I)
DEFAULT_DEFER_MIN = 5


def parse_defer(text: str) -> int | None:
    """Minutes the person wants to wait, or None. 'in 10 minutes' -> 10, 'in a while' -> 5."""
    m = DEFER_EXACT.search(text)
    if m:
        n, unit = m.group(1).lower(), m.group(2).lower()
        if n.startswith("half"):
            return 30  # "half an hour"
        val = int(n) if n.isdigit() else _NUM.get(n, DEFAULT_DEFER_MIN)
        return val * 60 if unit.startswith("h") else max(val, 1)
    return DEFAULT_DEFER_MIN if DEFER_VAGUE.search(text) else None


def is_start(text: str) -> bool:
    """'ok fine opening it' is a start; 'not opening it' (Firedrill) and 'I'll do it in a while' are not."""
    return bool(START_WORDS.search(text)) and not NEGATION.search(text) and parse_defer(text) is None


def parse_task(text: str) -> tuple[str, str | None]:
    """'I need to finish my pitch by 4:30.' -> ('your pitch', '4:30')."""
    text = text.strip().rstrip(".!?")
    m = DEADLINE.search(text)
    deadline = m.group(1).strip(" .") if m else None
    return clean_task(text[: m.start()] if m else text)[:200], deadline
