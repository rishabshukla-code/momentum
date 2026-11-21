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
    "five_minute": {
        "emoji": "⏱️",
        "label": "5-minute timer",
        "style": "proposes a 5-minute timer with permission to stop afterwards",
        "templates": [
            "Set a 5-minute timer for {task}. When it rings, you're allowed to stop.",
            "Five minutes on {task}. That's the whole deal.",
        ],
    },
    "body_double": {
        "emoji": "👥",
        "label": "Work with me",
        "style": "offers to keep them company while they work, like a study buddy",
        "templates": [
            "Let's do {task} together. I'll stay right here for the next 10 minutes.",
            "I'll keep you company while you start {task}. Go, I'm here.",
        ],
    },
    "first_line": {
        "emoji": "✍️",
        "label": "First line",
        "style": "asks a curious question about the very first thing they would write or do",
        "templates": [
            "What's the very first line of {task}? Just say it out loud.",
            "If {task} had a first sentence, what would it be?",
        ],
    },
    "music": {
        "emoji": "🎧",
        "label": "Focus song",
        "style": "suggests putting on a favourite focus song as the starting signal",
        "templates": [
            "Put on your focus song and open {task}. Start before the chorus.",
            "Headphones on, one song, {task} open. That's it.",
        ],
    },
    "change_place": {
        "emoji": "🪑",
        "label": "Change of scene",
        "style": "suggests moving somewhere new to make starting easier",
        "templates": [
            "Move to a different spot, then open {task}. New place, fresh start.",
            "Grab some water, sit somewhere else, and open {task}.",
        ],
    },
    "why_it_matters": {
        "emoji": "🌱",
        "label": "Why it matters",
        "style": "gently reminds them that this work moves them toward something they care about, without inventing details",
        "templates": [
            "{task} is one step toward something you care about. Take the step.",
            "Every bit of {task} is progress you'll be glad you made.",
        ],
    },
    # ---- firmer nudges: honest about consequences, never shaming or insulting ----
    "loss_aversion": {
        "emoji": "⌛",
        "label": "What you lose",
        "tone": "firm",
        "style": "points out, plainly, what waiting costs them (time, sleep, a free evening later); firm but not cruel",
        "templates": [
            "Every hour {task} waits is an hour you'll pay back later, probably tonight.",
            "Waiting on {task} isn't free. It's borrowing time from tomorrow.",
        ],
    },
    "future_regret": {
        "emoji": "🔮",
        "label": "Future regret",
        "tone": "firm",
        "style": "asks them to picture how they'll feel later if they keep putting it off; honest, not dramatic",
        "templates": [
            "Picture tomorrow: {task} still not started. Is that the version you want?",
            "Future you is going to look back at right now. Give them something better than 'later'.",
        ],
    },
    "reality_check": {
        "emoji": "🧭",
        "label": "Reality check",
        "tone": "firm",
        "style": "a calm, direct reality check that waiting won't make the task easier or go away",
        "templates": [
            "Honest check: {task} won't get easier by waiting. It just gets closer.",
            "{task} isn't going away. The only question is whether you start now or rushed.",
        ],
    },
    "tough_love": {
        "emoji": "💪",
        "label": "Tough love",
        "tone": "firm",
        "style": "short, firm coach voice: no excuses today, start now; direct but on their side, never insulting",
        "templates": [
            "No more warm-ups. Open {task} and do the first thing. Now.",
            "You know what to do. Stop negotiating with it. {task}, five minutes, go.",
        ],
    },
    "cost_of_delay": {
        "emoji": "📉",
        "label": "Cost of delay",
        "tone": "firm",
        "style": "explains that skipping today makes the next session longer and harder; matter-of-fact",
        "templates": [
            "Skip {task} today and tomorrow's session gets twice as long.",
            "Ten minutes on {task} now saves you an hour of panic later.",
        ],
    },
    "proud": {
        "emoji": "💛",
        "label": "Proud of you",
        "style": "warm encouragement that they are capable, without pressure",
        "templates": [
            "You're better at {task} than you think. Give it ten minutes.",
            "I believe you can make a good start on {task} today.",
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
