"""What Momentum says back after you answer. Calm and warm, varied, never the same line twice in a row."""
from __future__ import annotations

import random

REPLIES = {
    "started": [
        "That's lovely. I'll leave you to it.",
        "Good. The hardest part is already done.",
        "Perfect. Take it one step at a time.",
        "I'm glad. Go gently, you've got this.",
        "Nice. I'll stay quiet now and let you work.",
        "That's the spirit. Enjoy the focus.",
        "Wonderful. I'm proud of you for starting.",
    ],
    "snoozed": [
        "That's okay. Sounds like you're {excuse}. I'll come back with something smaller.",
        "No pressure. Next time, I'll make the first step tiny.",
        "I understand. I'll check in later, with something lighter.",
        "That's alright. We'll try a different way next time.",
        "Okay. Be easy on yourself. I'll be back a little later.",
    ],
    "deferred": [
        "Of course. I'll check back in {mins}.",
        "That's fine. Let's talk again in {mins}.",
        "Okay, {mins} then. I'll call you softly.",
        "Sounds good. I'll be here in {mins}.",
        "Sure. Take your {mins}, and I'll check in after.",
    ],
}
_last: dict[str, str] = {}


def minutes_text(m: int) -> str:
    if m % 60 == 0 and m >= 60:
        h = m // 60
        return "an hour" if h == 1 else f"{h} hours"
    return "a minute" if m == 1 else f"{m} minutes"


def pick(kind: str, **fmt) -> str:
    options = [r for r in REPLIES[kind] if r != _last.get(kind)] or REPLIES[kind]
    line = random.choice(options)
    _last[kind] = line
    return line.format(**fmt)
