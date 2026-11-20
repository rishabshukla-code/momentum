"""Demo profile: "Maya (demo, simulated)", three weeks of simulated history in the real database.

Maya is a synthetic person with hidden preferences. Momentum's real brain picks every
nudge for her over 21 days (morning and evening work blocks); her simulated answers
are stored in the same tables as real users, so the dashboard, /why logic and the
"only use what works" rule all run on it. Everything is clearly labelled simulated.

Run:
  python -m momentum.demo_profile            create (or recreate) Maya and print her report
  python -m momentum.demo_profile --report   only print the report
  python -m momentum.demo_profile --call     ring Momentum Phone with Maya's next nudge
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from sqlalchemy import delete, insert

from . import brain, store
from .nudges import ARMS, NUDGE_TYPES

DEMO_ID = "demo-maya"
DEMO_NAME = "Maya (demo, simulated)"
DAYS = 28

# Maya's hidden truth: chance she starts after each nudge type (unknown to Momentum).
MAYA = {
    "morning": {"tiny_step": .70, "five_minute": .65, "music": .55, "first_line": .45,
                "body_double": .40, "gentle": .10, "consequence": .10, "accountability": .05,
                "streak": .15, "reward": .20, "change_place": .25, "why_it_matters": .10, "proud": .10},
    "evening": {"consequence": .60, "reward": .55, "body_double": .50, "five_minute": .40,
                "tiny_step": .30, "gentle": .05, "accountability": .10, "streak": .15,
                "music": .20, "first_line": .20, "change_place": .15, "why_it_matters": .10, "proud": .05},
}
EXCUSES = {"morning": ["tired", "busy"], "evening": ["busy", "bored", "tired"]}


def build(seed: int = 11) -> int:
    rng = random.Random(seed)
    store.init_db()
    with store.engine.begin() as c:
        c.execute(delete(store.nudges).where(store.nudges.c.chat_id == DEMO_ID))
        c.execute(delete(store.tasks).where(store.tasks.c.chat_id == DEMO_ID))
        c.execute(delete(store.users).where(store.users.c.chat_id == DEMO_ID))
        c.execute(insert(store.users).values(chat_id=DEMO_ID, name=DEMO_NAME,
                                             created_at=datetime.now() - timedelta(days=DAYS)))
    task_id = store.add_task(DEMO_ID, "your thesis chapter", None)
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS)
    history: list[brain.Outcome] = []
    habit = {a: 0.0 for a in ARMS}
    rows = []
    for day in range(DAYS):
        habit = {a: h * 0.65 for a, h in habit.items()}
        for ctx, hour in (("morning", 9), ("evening", 20)):
            excuse = None
            for i in range(3):
                now = start + timedelta(days=day, hours=hour, minutes=15 * i)
                boost = {}
                if excuse:
                    from .integrations import EXCUSE_BOOST
                    boost = dict(EXCUSE_BOOST.get(excuse, {}))
                d = brain.choose(history, now, rng=rng, boost=boost, excuse=excuse)
                chance = MAYA[ctx].get(d.arm, .2) * (1 - min(habit[d.arm], .75))
                habit[d.arm] += 0.08
                ok = rng.random() < chance
                outcome = "started" if ok else rng.choice(["snoozed", "snoozed", "ignored"])
                excuse = rng.choice(EXCUSES[ctx]) if outcome == "snoozed" else None
                text = NUDGE_TYPES[d.arm]["templates"][0].format(
                    task="your thesis chapter", deadline="soon", streak=1)
                rows.append(dict(chat_id=DEMO_ID, task_id=task_id, arm=d.arm, context=d.context,
                                 text=f"{NUDGE_TYPES[d.arm]['emoji']} {text}", reason=d.reason,
                                 sent_at=now, outcome=outcome, excuse=excuse,
                                 responded_at=now + timedelta(minutes=2), message_id="sim"))
                history.append(brain.Outcome(d.arm, d.context, ok, now))
                if ok:
                    break
    with store.engine.begin() as c:
        c.execute(insert(store.nudges), rows)
    return len(rows)


def report() -> str:
    hist = store.history(DEMO_ID)
    if not hist:
        return "No demo profile yet. Run: python -m momentum.demo_profile"
    lines = [f"MOMENTUM REPORT: {DEMO_NAME}", f"{len(hist)} nudges over {DAYS} days "
             f"({sum(o.success for o in hist)} got her started)", ""]
    now = datetime.now()
    table = brain.win_rate_table(hist, now)
    for ctx in ("morning", "evening"):
        stats = []
        for a in ARMS:
            tries = [o for o in hist if o.arm == a and o.context == ctx]
            if tries:
                stats.append((a, sum(o.success for o in tries), len(tries), table[ctx][a]))
        stats.sort(key=lambda s: -s[3])
        label = lambda a: f"{NUDGE_TYPES[a]['emoji']} {NUDGE_TYPES[a]['label']}"
        lines.append(f"── {ctx.upper()} ──")
        lines.append("  ✅ Worked on her:")
        for a, w, n, r in stats:
            if w and r >= brain.PROVEN_MIN_RATE:
                lines.append(f"     {label(a):22s} started {w} of {n} times  ({r:.0%})")
        lines.append("  ❌ Did not work on her:")
        for a, w, n, r in sorted(stats, key=lambda s: (s[1] / s[2], -s[2])):
            if not (w and r >= brain.PROVEN_MIN_RATE):
                lines.append(f"     {label(a):22s} started {w} of {n} times")
        lines.append("")
    for ctx, hour in (("morning", 9), ("evening", 20)):
        when = now.replace(hour=hour, minute=0)
        pr = brain.proven_arms(hist, {a: table[ctx][a] for a in ARMS}, ctx)
        d = brain.choose(hist, when)
        lines.append(f"Momentum will now only use for {ctx}: "
                     + ", ".join(NUDGE_TYPES[a]["label"] for a in pr))
        lines.append(f"  next {ctx} nudge → {NUDGE_TYPES[d.arm]['label']}: {d.reason}")
    return "\n".join(lines)


def call() -> None:
    from . import agent, voice
    voice.set_call(DEMO_ID, "web")
    if not store.active_task(DEMO_ID):
        store.add_task(DEMO_ID, "your thesis chapter", None)
    r = agent.send_nudge(DEMO_ID)
    print("ringing Momentum Phone for Maya:", r["text"], "|", r["reason"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--call", action="store_true")
    a = ap.parse_args()
    if a.call:
        return call()
    if not a.report:
        print(f"created {build()} simulated nudges for {DEMO_NAME}\n")
    print(report())


if __name__ == "__main__":
    main()
