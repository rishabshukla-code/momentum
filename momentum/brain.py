"""The learning brain: discounted Thompson sampling with a fatigue penalty.

Each nudge type keeps a win/miss record per context (time of day).
  * Old results fade (DECAY_PER_DAY), so it notices when a nudge stops working.
  * Recently used types get a fatigue penalty, so it rotates instead of repeating.
  * Thompson sampling handles explore vs exploit automatically.

The brain is a set of pure functions over the nudge history, so the live bot and
the simulator share exactly the same logic.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime

from .nudges import ARMS

DECAY_PER_DAY = 0.85  # yesterday's result counts 85% as much as today's
FATIGUE_STRENGTH = 0.35  # max penalty right after a type was used
FATIGUE_HALF_LIFE_H = 18.0  # penalty halves every 18 hours
CONTEXT_SHARE = 0.3  # how much other time-of-day data informs this context


@dataclass
class Outcome:
    arm: str
    context: str
    success: bool
    at: datetime


@dataclass
class Decision:
    arm: str
    context: str
    scores: dict = field(default_factory=dict)  # arm -> final score
    win_rates: dict = field(default_factory=dict)  # arm -> estimated win rate
    fatigue: dict = field(default_factory=dict)  # arm -> penalty
    reason: str = ""


def context_for(now: datetime) -> str:
    h = now.hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    if 18 <= h < 23:
        return "evening"
    return "late_night"


def _posterior(history: list[Outcome], context: str, now: datetime, prior: dict | None):
    """Return {arm: (alpha, beta)} with time decay and partial sharing across contexts."""
    post = {}
    for arm in ARMS:
        a0, b0 = (prior or {}).get(arm, (1.0, 1.0))
        post[arm] = [a0, b0]
    for o in history:
        if o.arm not in post:
            continue
        age_days = max((now - o.at).total_seconds() / 86400, 0)
        w = DECAY_PER_DAY**age_days
        if o.context != context:
            w *= CONTEXT_SHARE
        if o.success:
            post[o.arm][0] += w
        else:
            post[o.arm][1] += w
    return post


def _fatigue(history: list[Outcome], now: datetime) -> dict:
    pen = {arm: 0.0 for arm in ARMS}
    for o in history:
        hours = max((now - o.at).total_seconds() / 3600, 0)
        pen[o.arm] += FATIGUE_STRENGTH * 0.5 ** (hours / FATIGUE_HALF_LIFE_H)
    return {a: min(p, 0.6) for a, p in pen.items()}


def choose(
    history: list[Outcome],
    now: datetime,
    prior: dict | None = None,
    boost: dict | None = None,
    rng: random.Random | None = None,
    excuse: str | None = None,
) -> Decision:
    """Pick the next nudge type.

    prior: optional {arm: (alpha, beta)} head start, e.g. from onboarding.
    boost: optional {arm: +score} nudges from the excuse classifier.
    """
    rng = rng or random
    context = context_for(now)
    post = _posterior(history, context, now, prior)
    fatigue = _fatigue(history, now)
    scores, rates = {}, {}
    for arm, (a, b) in post.items():
        sample = rng.betavariate(a, b)
        rates[arm] = a / (a + b)
        scores[arm] = sample - fatigue[arm] + (boost or {}).get(arm, 0.0)
    # Once we know someone, only use nudge types that have actually worked on them.
    proven = proven_arms(history, rates, context)
    pool = proven or list(scores)
    # An excuse decides which kinds of nudge are allowed; learning picks among them.
    fitting = [a for a, v in (boost or {}).items() if v > 0 and a in scores] if excuse else []
    fitting = [a for a in fitting if a in pool] or ([] if proven else fitting)
    just_declined = max(history, key=lambda o: o.at).arm if history else None
    choices = fitting or pool
    if len(choices) > 1 and just_declined in choices:
        choices = [a for a in choices if a != just_declined]  # rotate: don't repeat a declined nudge
    arm = max(choices, key=scores.get)

    best_rate_arm = max(rates, key=rates.get)
    n_tries = sum(1 for o in history if o.arm == arm and o.context == context)
    if n_tries == 0 and not any(o.arm == arm for o in history):
        reason = f"exploring '{arm}': never tried on you yet"
    elif arm == best_rate_arm:
        reason = f"'{arm}' has the best recent record for {context} ({rates[arm]:.0%})"
    elif fatigue[best_rate_arm] > 0.1:
        reason = (
            f"'{best_rate_arm}' works best but was used recently (fatigue "
            f"-{fatigue[best_rate_arm]:.2f}), so rotating to '{arm}'"
        )
    elif n_tries < 3:
        reason = f"exploring '{arm}': only {n_tries} tries in {context} so far"
    else:
        reason = f"'{arm}' won this round's sampling ({rates[arm]:.0%} est.)"
    if proven:
        retired = len(scores) - len(proven)
        if any(o.arm == arm and o.success and o.context == context for o in history):
            reason = (f"'{arm}' has worked on you before ({rates[arm]:.0%} in the {context}); "
                      f"{retired} nudge types that didn't work are retired")
        else:
            reason = f"giving '{arm}' a fair try before deciding; {retired} types that didn't work are retired"
    if boost and boost.get(arm, 0) > 0:
        reason = (f"you said you were {excuse}, and '{arm}' suits that; {reason}"
                  if excuse else reason + " (boosted by your last reply)")

    return Decision(arm, context, scores, rates, fatigue, reason)


PROVEN_MIN_HISTORY = 30  # answers needed before we start retiring nudge types
PROVEN_MIN_RATE = 0.30
FAIR_TRIES = 2  # a nudge type is only retired after this many tries at that time of day
SECOND_CHANCE_DAYS = 60  # retirement expires: after two months a retired type can be tried again (14 days re-tested too often)


def proven_arms(history: list[Outcome], rates: dict, context: str | None = None) -> list[str]:
    """The pool to choose from once we know someone: types that worked here, plus types that
    haven't had a fair try yet. Types that had a fair try and never worked are retired."""
    if len(history) < PROVEN_MIN_HISTORY:
        return []
    latest = max(o.at for o in history)
    # only the last 14 days count, so a retired type gets a second chance later (people change)
    here = [o for o in history if (context is None or o.context == context)
            and (latest - o.at).days < SECOND_CHANCE_DAYS]
    tries = {a: sum(o.arm == a for o in here) for a in rates}
    won = {o.arm for o in here if o.success}
    pool = [a for a in rates if tries[a] < FAIR_TRIES or (a in won and rates[a] >= PROVEN_MIN_RATE)]
    return [] if len(pool) == len(rates) else pool


def retired_arms(history: list[Outcome], rates: dict, context: str | None = None) -> list[str]:
    """Types that had a fair try at this time of day and didn't work."""
    pool = proven_arms(history, rates, context)
    return [a for a in rates if pool and a not in pool]


def win_rate_table(history: list[Outcome], now: datetime) -> dict:
    """{context: {arm: estimated win rate}} for the dashboard heatmap."""
    out = {}
    for ctx in ("morning", "afternoon", "evening", "late_night"):
        post = _posterior(history, ctx, now, None)
        out[ctx] = {arm: a / (a + b) for arm, (a, b) in post.items()}
    return out


def onboarding_prior(answer: str | None) -> dict:
    """Turn 'what usually gets you moving?' into a small head start."""
    mapping = {
        "deadlines": "consequence",
        "small steps": "tiny_step",
        "someone counting": "accountability",
        "rewards": "reward",
    }
    arm = mapping.get((answer or "").lower())
    return {arm: (3.0, 1.0)} if arm else {}
