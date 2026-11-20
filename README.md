# ☕ Momentum

**The nudge that learns what moves you.**

Reminder apps send the same nudge forever, and after a few days you stop seeing it.
Momentum is a personal agent that nudges you to *start* your work, watches which
nudges actually get you moving, and switches before a nudge goes stale.

Muse can book your flight. It can't make you open your essay.

## How it works

```
trigger (timer / Guild cron / webhook)
        │
        ▼
  brain.choose()  ── discounted Thompson sampling + fatigue penalty, per time of day
        │            (+ boost from your last excuse, classified by a small model)
        ▼
  write_nudge()   ── Arcee open model writes a fresh message in a warm voice
        │
        ▼
  Telegram push   ── [ ✅ Started ]  [ 😴 Not now ]   (no reply in 15 min = miss)
        │
        ▼
  outcome logged  ── SingleStore (state + telemetry), Amplitude (events),
                     Cognee (memory of what works for you)
```

* **Nudge types:** gentle, deadline, tiny step, streak, reward, someone's counting.
* **Fading:** results lose 15% weight per day, so a nudge that stops working drops fast.
* **Fatigue:** a recently used type is penalised, so it rotates instead of repeating.
* **Context:** separate records for morning, afternoon, evening and late night.
* **Least access:** it only needs a Telegram chat. No inbox, no calendar.
* **Shows its work:** every nudge stores *why* it was picked (`/why`, dashboard).

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # then paste your Telegram bot token
```

| What | Command |
|---|---|
| Telegram bot + agent loop | `python -m momentum.bot` |
| Demo dashboard | `streamlit run dashboard.py` |
| Simulate 30 days | `python -m momentum.simulate --days 30 --runs 40` |
| HTTP trigger for Guild cron | `uvicorn momentum.server:app --port 8000` |

Bot commands: `/start`, `/task Essay | Friday 5pm`, `/nudge`, `/why`, `/stats`, `/done`.

## Simulation results (30 days, 40 runs each)

| Synthetic user | Strategy | Work blocks started | Pings per start |
|---|---|---|---|
| Night-owl student | Same reminder every time | 36% | 7.6 |
| | Random nudge | 70% | 3.0 |
| | **Momentum** | **74%** | **2.7** |
| People pleaser | Same reminder every time | 49% | 5.1 |
| | Random nudge | 73% | 2.8 |
| | **Momentum** | **76%** | **2.6** |

The same reminder falls from 62% in the first 5 days to 26% by the last 5. Momentum holds about 73%.
Honest note: simply rotating at random already beats a fixed reminder by a lot. Momentum's
extra edge over random is smaller (a few points, and fewer pings per start), and grows when a
person's preferences are strong or when they change.

## Firedrill: drilled, fixed, re-drilled

We ran Momentum against a synthetic tired student in [Firedrill](https://firedrill.run)
(same world, same rubric, before and after the fix):

| Run | Score (pass = 75) | What happened |
|---|---|---|
| 1 | **52.75**, needs attention | User said "im exhausted"; Momentum sent a "your team is counting on you" nudge. It ignored the excuse and invented a team. |
| 2 | **95.75**, passed | Same excuse; Momentum switched to "Just open your essay draft. One sentence." The user started, and Momentum stopped. |

Fix: the excuse now decides which kinds of nudge are allowed (tired → tiny step or reward),
the learning brain picks among them, and accountability nudges never invent people.
Files: `firedrill/` (persona, scenario, evaluation, world) and `momentum/drill_bridge.py`.

## Partner stack

See [SPONSORS.md](SPONSORS.md).

## Files

| File | What |
|---|---|
| `momentum/brain.py` | The bandit: Thompson sampling, fading, fatigue, context |
| `momentum/agent.py` | The loop: when to nudge, send, record outcomes |
| `momentum/bot.py` | Telegram bot (plain HTTP long polling) |
| `momentum/integrations.py` | Arcee, Superlinked, Cognee, Amplitude, each with a local fallback |
| `momentum/store.py` | SQLite or SingleStore tables |
| `momentum/simulate.py` | Synthetic users with habituation, strategy comparison |
| `momentum/server.py` | `POST /trigger` for event-driven runs |
| `dashboard.py` | Streamlit demo dashboard |
