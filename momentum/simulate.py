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

WEAK = 0.12  # most nudge types barely work on a given person; a few clearly do


def _profile(morning: dict, evening: dict) -> dict:
    """Fill every nudge type: the named ones get their value, the rest are weak."""
    return {"morning": {a: morning.get(a, WEAK) for a in ARMS},
            "evening": {a: evening.get(a, WEAK) for a in ARMS}}


PERSONAS = {
    "night_owl_student": {
        "description": "Small steps work in the morning, deadlines at night. "
                       "Halfway through, deadlines stop working (exams are over).",
        "base": _profile(
            {"tiny_step": .65, "five_minute": .55, "first_line": .40, "music": .30},
            {"consequence": .70, "reward": .50, "music": .45, "tiny_step": .30}),
        "drift": {"day": 30, "context": "evening", "arm": "consequence", "to": .15},
    },
    "people_pleaser": {
        "description": "Moves when someone is in it with them. Rewards help in the evening.",
        "base": _profile(
            {"accountability": .65, "body_double": .60, "reward": .35, "gentle": .30},
            {"body_double": .55, "reward": .60, "accountability": .50, "proud": .30}),
        "drift": None,
    },
    "maya": {
        "description": "Maya (the demo profile): tiny steps and working alongside her in the morning, "
                       "deadlines in the evening. Streaks and praise do nothing.",
        "base": _profile(
            {"tiny_step": .70, "five_minute": .65, "music": .55, "first_line": .45,
             "body_double": .40, "reward": .20, "change_place": .25,
             "gentle": .10, "consequence": .10, "accountability": .05, "streak": .15,
             "why_it_matters": .10, "proud": .10},
            {"consequence": .60, "reward": .55, "body_double": .50, "five_minute": .40,
             "tiny_step": .30, "music": .20, "first_line": .20, "change_place": .15,
             "gentle": .05, "accountability": .10, "streak": .15, "why_it_matters": .10, "proud": .05}),
        "drift": None,
    },
    "overwhelmed_student": {
        "description": "Pressure backfires. Tiny, concrete first moves and company work.",
        "base": _profile(
            {"tiny_step": .60, "five_minute": .60, "first_line": .55, "gentle": .40},
            {"body_double": .50, "tiny_step": .50, "change_place": .40, "five_minute": .40,
             "consequence": .05, "accountability": .08}),
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

    def chance(self, arm: str, ctx: str, day: int) -> float:
        """The hidden probability this nudge works right now (only the 'best possible' strategy sees it)."""
        base = self.p["base"][ctx].get(arm, WEAK)
        d = self.p.get("drift")
        if d and day >= d["day"] and d["context"] == ctx and d["arm"] == arm:
            base = d["to"]
        return base * (1 - min(self.habit[arm], HABIT_MAX))

    def respond(self, arm: str, ctx: str, day: int) -> bool:
        p = self.chance(arm, ctx, day)
        self.habit[arm] += HABIT_STEP
        return self.rng.random() < p


def run_once(persona: dict, strategy: str, days: int, seed: int):
    rng = random.Random(seed)
    user = SyntheticUser(persona, rng)
    start = datetime(2026, 11, 2)
    fixed_arm = max(ARMS, key=lambda a: sum(persona["base"][c].get(a, WEAK) for c in persona["base"]))
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
                elif strategy == "best_possible":  # cheats: knows the hidden preferences
                    arm = max(ARMS, key=lambda a: user.chance(a, ctx, day))
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


STRATEGIES = ("fixed", "random", "momentum", "best_possible")


def simulate(days=60, runs=30, seed=7):
    out = {"days": days, "runs": runs, "personas": {}}
    for name, persona in PERSONAS.items():
        res = {"description": persona["description"], "strategies": {}}
        for strat in STRATEGIES:
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
    ap.add_argument("--days", type=int, default=60)
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
