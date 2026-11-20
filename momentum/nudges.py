"""The nudge types (the bandit's "arms") and fallback messages in Momentum's warm voice.

The LLM writes a fresh message for the chosen type. These templates are used
when no LLM is configured, or when the LLM call fails.
"""
import random
import re

NUDGE_TYPES = {
    "gentle": {
        "emoji": "☕",
        "label": "Gentle",
        "style": "soft and warm, like someone at home checking in",
        "templates": [
            "Chai's ready. Maybe start on {task}?",
            "Hey, no pressure. Just a little time on {task}?",
            "Thinking of you. {task} is waiting whenever you're ready.",
        ],
    },
    "consequence": {
        "emoji": "⏰",
        "label": "Deadline",
        "style": "honest about what happens if they wait, but caring, never harsh; only mention a deadline if one was given",
        "templates": [
            "{task} is due {deadline}. Start now and you'll still sleep tonight.",
            "Future you will thank you. {task}, due {deadline}.",
            "If you start {task} now, tomorrow gets a lot easier.",
            "Future you will thank you for starting {task} today.",
        ],
    },
    "tiny_step": {
        "emoji": "🪜",
        "label": "Tiny step",
        "style": "asks for one absurdly small first action, nothing more",
        "templates": [
            "Just open {task}. That's it. One sentence.",
            "Two minutes on {task}. You can stop after that.",
            "Only open the file for {task}. I'm not asking for more.",
        ],
    },
    "streak": {
        "emoji": "🔥",
        "label": "Streak",
        "style": "mentions their recent progress and invites them not to break it",
        "templates": [
            "You started on time {streak} times recently. Keep it going with {task}?",
            "You've been showing up. Let's not break that. {task}?",
        ],
    },
    "reward": {
        "emoji": "🍪",
        "label": "Reward",
        "style": "offers a small treat or break after a short focused stretch",
        "templates": [
            "25 minutes on {task}, then snacks. Deal?",
            "Do a short sprint on {task}, then you've earned a break.",
        ],
    },
    "accountability": {
        "emoji": "🤝",
        "label": "Someone's counting",
        "style": "reminds them who benefits from this work, usually future them; never invent a team, friend or person they did not mention",
        "templates": [
            "Future you is counting on {task}. Let's hand them a head start.",
            "Do a little of {task} now, as a favour to tomorrow's you.",
        ],
    },
}

_VERB = re.compile(
    r"^(?:i\s+)?(?:(?:really|probably|just|maybe|actually|kinda)\s+)*"
    r"(?:gotta|need|have|got|want|should|must)?\s*(?:to\s+)?"
    r"(?:(?:really|probably|just|maybe|actually)\s+)*"
    r"(?:finish|complete|do|write|work\s+on|start(?:\s+on)?|study\s+for|prep(?:are)?\s+for|get\s+through)?\s*",
    re.I,
)


def clean_task(text: str) -> str:
    """'I need to finish my essay draft' -> 'your essay draft'."""
    t = text.strip(" .!")
    t = _VERB.sub("", t, count=1).strip()
    t = re.sub(r"^my\s+", "your ", t, flags=re.I)
    return t or text.strip() or "your work"

ARMS = list(NUDGE_TYPES)


def fallback_text(arm: str, task: str, deadline: str | None, streak: int = 0) -> str:
    t = NUDGE_TYPES[arm]
    options = t["templates"]
    if not deadline:  # never invent a deadline the user did not give
        options = [o for o in options if "{deadline}" not in o] or options
    msg = random.choice(options).format(
        task=task, deadline=deadline or "soon", streak=max(streak, 1)
    )
    # start every sentence with a capital, even when it opens with the task name
    msg = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), msg)
    return f"{t['emoji']} {msg}"
