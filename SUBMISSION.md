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

- **It learns what works on you.** A multi-armed bandit (Thompson sampling) tracks 13 nudge styles (gentle, deadline, tiny step, 5-minute timer, work-with-me, first line, focus song, reward, and more) separately for morning, afternoon, evening and late night.
- **It knows nudges wear off.** Old results fade and recently used styles get a fatigue penalty, so it rotates before a nudge goes stale. In a 60-day simulation with four synthetic people, a fixed reminder wears off (about 60% → 34%) while Momentum climbs (about 58% → 76%), reaching ~82% of a strategy that secretly knows the answers.
- **It keeps only what works on you.** After about 30 answers it retires nudge types that never got you started at that time of day and only uses the ones that did. In our simulated demo profile "Maya" (4 weeks), mornings belong to a tiny step, working alongside her or a reward; evenings only to a deadline; streaks and "proud of you" were retired.
- **It listens to your excuse.** Say "too tired" and it switches to a tiny step or a reward instead of more pressure. Say no three times and it backs off kindly.
- **It shows its work.** Every nudge stores why it was chosen ("you said you were tired, and 'tiny_step' suits that"), visible with /why and in the dashboard.
- **It can call you.** Momentum Phone simulates a real phone call: it rings, you accept or decline, unanswered calls go to voicemail, Momentum speaks the nudge, and you answer out loud. Real calls through Twilio are built too (blocked today only by Twilio's trial limits), and if a call fails the nudge falls back to Telegram.
- **Least access that works.** It needs one chat or the call page. No inbox, calendar or screen access.

We tested it against synthetic users in Firedrill and fixed what they found:
- Tired student: 52.75 → 95.75 (it had ignored "exhausted" and invented a team that didn't exist)
- Stubborn student who never starts: 57.5 → 92.25 (it read "not opening it" as a start)

## Tools used
- **Firedrill**: two scenarios with synthetic personas and rubrics, run against Momentum through a jsonl-process bridge; drilled, fixed, re-drilled on the same worlds
- **SingleStore**: all agent state and telemetry (users, tasks, every nudge with its reason and outcome) on a Helios Starter cluster over TLS
- **Amplitude**: `nudge_sent` and `nudge_outcome` events for every decision, via the official Python SDK
- **Telegram Bot API**: nudge delivery with inline buttons
- **Momentum Phone**: browser call simulation (WebAudio ringtone, speech synthesis), spoken answers transcribed with **AssemblyAI**; **Twilio** voice integration for real calls
- **Python, SQLAlchemy, FastAPI** (`/trigger` endpoint so a scheduler can drive the agent), **Streamlit** (simulation and live decision dashboard)
- **Claude API** (Claude Opus 5.5, official Anthropic SDK): writes every nudge fresh in the chosen style and Momentum's warm voice, never inventing facts; falls back to built-in templates on any error
- **Arcee**: the same writer slot works with Arcee's open models; not active because hackathon credits weren't available
- Built with **Claude Code**

## Team
<names and contact emails>
