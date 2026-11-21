"""What Momentum says back after you answer. Varied, and never the same line twice in a row."""
from __future__ import annotations

import random

REPLIES = {
    "started": [
        "Love that. Go go go!",
        "Yes! I'll leave you to it.",
        "That's the hardest part done. Go get it.",
        "Perfect. I'll stay quiet now, you've got this.",
        "Look at you, starting. I'm proud of you.",
        "Great move. Enjoy the momentum.",
        "Brilliant. Off you go!",
    ],
    "snoozed": [
        "No worries, sounds like you're {excuse}. I'll come back with something smaller.",
        "That's okay. Next time I'll make the first step tiny.",
        "Got it, {excuse} happens. I'll check in later with something lighter.",
        "Fair enough. I'll try a different way next time.",
        "All good. I'll be back with an easier ask.",
    ],
    "deferred": [
        "Sure, I'll check back in {mins}.",
        "No problem. Talk to you in {mins}.",
        "Deal. I'll call you again in {mins}.",
        "Okay, {mins} it is. I'll be back.",
        "Sounds good. See you in {mins}.",
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
