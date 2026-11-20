# Submission: Momentum

Copy each section into the form at https://tokensand.com/personalagenthack/submit

## Project name
Momentum

## One-liner
The nudge that learns what moves you: a personal agent that figures out which nudges actually get you to start working, and switches before they wear off.

## GitHub repository
https://github.com/rishabshukla-code/momentum

## Demo video
<paste your video link here>

## What we built
Reminder apps send the same nudge forever, and after a few days you stop seeing it. Agents like Meta's Muse can book your flight, but they can't make you open your essay.

Momentum is a personal agent that lives outside the chat window. You tell it what you need to work on; it nudges you on Telegram on its own schedule, with ✅ Started / 😴 Not now buttons. Every reply teaches it something:

- **It learns what works on you.** A multi-armed bandit (Thompson sampling) tracks six nudge styles (gentle, deadline, tiny step, streak, reward, future-you) separately for morning, afternoon, evening and late night.
- **It knows nudges wear off.** Old results fade and recently used styles get a fatigue penalty, so it rotates before a nudge goes stale. In a 30-day simulation, a fixed reminder drops from 62% to 26% effectiveness while Momentum holds about 75%.
- **It listens to your excuse.** Say "too tired" and it switches to a tiny step or a reward instead of more pressure. Say no three times and it backs off kindly.
- **It shows its work.** Every nudge stores why it was chosen ("you said you were tired, and 'tiny_step' suits that"), visible with /why and in the dashboard.
- **Least access that works.** It needs one Telegram chat. No inbox, calendar or screen access.

We tested it against synthetic users in Firedrill and fixed what they found:
- Tired student: 52.75 → 95.75 (it had ignored "exhausted" and invented a team that didn't exist)
- Stubborn student who never starts: 57.5 → 92.25 (it read "not opening it" as a start)

## Tools used
- **Firedrill**: two scenarios with synthetic personas and rubrics, run against Momentum through a jsonl-process bridge; drilled, fixed, re-drilled on the same worlds
- **SingleStore**: all agent state and telemetry (users, tasks, every nudge with its reason and outcome) on a Helios Starter cluster over TLS
- **Amplitude**: `nudge_sent` and `nudge_outcome` events for every decision, via the official Python SDK
- **Telegram Bot API**: nudge delivery with inline buttons
- **Python, SQLAlchemy, FastAPI** (`/trigger` endpoint so a scheduler can drive the agent), **Streamlit** (simulation and live decision dashboard)
- **Arcee**: integration built for writing fresh nudges with a small open model; not active in the demo because hackathon credits weren't available, so Momentum uses its own templates
- Built with **Claude Code**

## Team
<names and contact emails>
