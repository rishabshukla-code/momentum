"""Simulate weeks of nudges in seconds, against synthetic users.

Each synthetic user has a hidden response chance per nudge type and time of day,
plus habituation: every time a type is used, it works a bit less, and that wears
off again over a few days. That is the "same nudge won't work every time" effect.

Strategies compared:
  fixed     - always the nudge that works best on day 1 (what most apps do)
  random    - a random nudge type each time
  momentum  - the real brain from brain.py

Run:  python -m momentum.simulate --days 30 --runs 30
Output: sim_results.json (read by the dashboard)
The personas are also exported to personas.json for running the same drill in Firedrill.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from . import brain
from .nudges import ARMS

ROOT = Path(__file__).resolve().parent.parent

PERSONAS = {
    "night_owl_student": {
        "description": "Ignores soft reminders. Small steps work in the morning, deadlines at night.",
        "base": {
            "morning": {"gentle": 0.20, "consequence": 0.35, "tiny_step": 0.65, "streak": 0.40,
                        "reward": 0.30, "accountability": 0.35},
            "evening": {"gentle": 0.20, "consequence": 0.70, "tiny_step": 0.35, "streak": 0.40,
                        "reward": 0.50, "accountability": 0.40},
        },
        # Halfway through, the deadline nudge loses its bite (e.g. after exams).
        "drift": {"day": 15, "context": "evening", "arm": "consequence", "to": 0.30},
    },
    "people_pleaser": {
        "description": "Moves when someone else is counting on them. Rewards help when tired.",
        "base": {
            "morning": {"gentle": 0.30, "consequence": 0.30, "tiny_step": 0.40, "streak": 0.35,
                        "reward": 0.35, "accountability": 0.65},
            "evening": {"gentle": 0.25, "consequence": 0.35, "tiny_step": 0.40, "streak": 0.30,
                        "reward": 0.60, "accountability": 0.55},
        },
        "drift": None,
    },
}

HABIT_STEP = 0.08  # each exposure to a type adds this much habituation
HABIT_DECAY = 0.65  # habituation kept per day
HABIT_MAX = 0.75
NUDGES_PER_BLOCK = 3
BLOCKS = [("morning", 9), ("evening", 21)]  # two work blocks a day


class SyntheticUser:
    def __init__(self, persona: dict, rng: random.Random):
        self.p = persona
        self.rng = rng
        self.habit = {a: 0.0 for a in ARMS}

    def new_day(self):
        for a in self.habit:
            self.habit[a] *= HABIT_DECAY

    def respond(self, arm: str, ctx: str, day: int) -> bool:
        base = self.p["base"][ctx][arm]
        d = self.p.get("drift")
        if d and day >= d["day"] and d["context"] == ctx and d["arm"] == arm:
            base = d["to"]
        chance = base * (1 - min(self.habit[arm], HABIT_MAX))
        self.habit[arm] += HABIT_STEP
        return self.rng.random() < chance


def run_once(persona: dict, strategy: str, days: int, seed: int):
    rng = random.Random(seed)
    user = SyntheticUser(persona, rng)
    start = datetime(2026, 11, 2)
    fixed_arm = max(ARMS, key=lambda a: sum(persona["base"][c][a] for c in persona["base"]))
    history: list[brain.Outcome] = []
    daily, picks = [], []
    sent = starts = first_try = 0
    for day in range(days):
        user.new_day()
        started_blocks, day_picks = 0, {a: 0 for a in ARMS}
        for ctx, hour in BLOCKS:
            for i in range(NUDGES_PER_BLOCK):
                sent += 1
                now = start + timedelta(days=day, hours=hour, minutes=15 * i)
                if strategy == "fixed":
                    arm = fixed_arm
                elif strategy == "random":
                    arm = rng.choice(ARMS)
                else:
                    arm = brain.choose(history, now, rng=rng).arm
                day_picks[arm] += 1
                ok = user.respond(arm, ctx, day)
                history.append(brain.Outcome(arm, brain.context_for(now), ok, now))
                if ok:
                    started_blocks += 1
                    starts += 1
                    first_try += i == 0
                    break
        daily.append(started_blocks / len(BLOCKS))
        picks.append(day_picks)
    end = start + timedelta(days=days)
    blocks = days * len(BLOCKS)
    extra = {"first_nudge_rate": first_try / blocks,
             "nudges_per_start": sent / max(starts, 1)}
    return daily, picks, brain.win_rate_table(history, end), fixed_arm, extra


def simulate(days=30, runs=30, seed=7):
    out = {"days": days, "runs": runs, "personas": {}}
    for name, persona in PERSONAS.items():
        res = {"description": persona["description"], "strategies": {}}
        for strat in ("fixed", "random", "momentum"):
            all_daily, pick_tot, last_table = [], [{a: 0 for a in ARMS} for _ in range(days)], None
            fnr = nps = 0.0
            for r in range(runs):
                daily, picks, table, fixed_arm, extra = run_once(persona, strat, days, seed + r)
                fnr += extra["first_nudge_rate"] / runs
                nps += extra["nudges_per_start"] / runs
                all_daily.append(daily)
                for d in range(days):
                    for a in ARMS:
                        pick_tot[d][a] += picks[d][a]
                if last_table is None:
                    last_table = {c: {a: 0.0 for a in ARMS} for c in table}
                for c in table:
                    for a in ARMS:
                        last_table[c][a] += table[c][a] / runs
            mean_daily = [sum(x[d] for x in all_daily) / runs for d in range(days)]
            res["strategies"][strat] = {
                "daily_start_rate": mean_daily,
                "overall": sum(mean_daily) / days,
                "first_nudge_rate": fnr,
                "nudges_per_start": nps,
                "picks_per_day": [{a: v / runs for a, v in p.items()} for p in pick_tot],
                "learned": last_table,
            }
            res["fixed_arm"] = fixed_arm
        out["personas"][name] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--runs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    out = simulate(a.days, a.runs, a.seed)
    (ROOT / "sim_results.json").write_text(json.dumps(out, indent=1))
    (ROOT / "personas.json").write_text(json.dumps(PERSONAS, indent=1))
    for name, res in out["personas"].items():
        print(f"\n{name}: {res['description']}")
        for strat, s in res["strategies"].items():
            first = sum(s["daily_start_rate"][:5]) / 5
            last = sum(s["daily_start_rate"][-5:]) / 5
            print(f"  {strat:9s} started {s['overall']:.0%}  (first 5 days {first:.0%},"
                  f" last 5 days {last:.0%})  first-nudge {s['first_nudge_rate']:.0%}"
                  f"  pings/start {s['nudges_per_start']:.2f}")
    print("\nWrote sim_results.json and personas.json")


if __name__ == "__main__":
    main()
