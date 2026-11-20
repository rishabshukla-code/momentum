"""The nudge types (the bandit's "arms") and fallback messages in Momentum's warm voice.

The LLM writes a fresh message for the chosen type. These templates are used
when no LLM is configured, or when the LLM call fails.
"""
import random

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
        "style": "honest about the deadline and what happens if they wait, but caring, never harsh",
        "templates": [
            "{task} is due {deadline}. Start now and you'll still sleep tonight.",
            "Future you will thank you. {task}, due {deadline}.",
            "If you start {task} now, tomorrow gets a lot easier.",
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
        "style": "reminds them someone else is relying on this work",
        "templates": [
            "Someone's counting on {task}. Let's get a piece of it done.",
            "Your team will be happy to see progress on {task} today.",
        ],
    },
}

ARMS = list(NUDGE_TYPES)


def fallback_text(arm: str, task: str, deadline: str | None, streak: int = 0) -> str:
    t = NUDGE_TYPES[arm]
    msg = random.choice(t["templates"]).format(
        task=task, deadline=deadline or "soon", streak=max(streak, 1)
    )
    return f"{t['emoji']} {msg}"
