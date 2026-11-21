"""What Momentum says back after you answer. Calm, warm and spoken the way a person talks
(soft openings, one light filler or pause, per AssemblyAI's TTS prompting guide).
Varied, and never the same line twice in a row."""
from __future__ import annotations

import random

REPLIES = {
    "started": [
        "Oh, that's lovely... I'll leave you to it.",
        "Okay, good. The, uh, hardest part is already done.",
        "Mm, perfect. Just take it one step at a time.",
        "Oh, I'm glad. Go gently, okay? You've got this.",
        "Nice... I'll, um, stay quiet now and let you work.",
        "Okay, that's the spirit. Enjoy the focus.",
        "Aw, I'm proud of you for starting. Really.",
    ],
    "snoozed": [
        "That's okay... sounds like you're {excuse}. I'll come back with something, um, smaller.",
        "Mm, no pressure. Next time I'll make the first step really tiny.",
        "I get it. I'll check in later, with something, uh, lighter.",
        "That's alright... we'll try a different way next time, okay?",
        "Okay. Be easy on yourself, yeah? I'll be back a little later.",
    ],
    "deferred": [
        "Of course, um, I'll check back in {mins}.",
        "Yeah, that's fine... let's talk again in {mins}.",
        "Okay, {mins} then. I'll, uh, call you softly.",
        "Sounds good. I'll be here in {mins}, okay?",
        "Sure... take your {mins}, and I'll check in after.",
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
