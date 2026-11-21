# Momentum: demo video script (about 3½ minutes)

## Before you hit record (2 minutes)

- [ ] `.env` has `SECONDS_PER_MINUTE=2` (demo clock) and the bot + server are running
- [ ] **Edge tab 1:** `http://localhost:8000/phone` → click **Turn on Momentum Phone**, volume up
- [ ] **Edge tab 2:** `http://localhost:8501` (dashboard)
- [ ] **Telegram** open with @momentum_hack_bot (phone or web.telegram.org)
- [ ] Send `/task Hackathon pitch | today 5pm` now, so the call is about the pitch
- [ ] Recorder: **Win + Alt + R** starts/stops (Xbox Game Bar), mic on
- [ ] Optional: README open on GitHub at the Firedrill table

Speak slowly. If something glitches, keep going and narrate it. Judges care about the story.

---

## Scene 1: The problem (0:00 – 0:20)
**Screen:** dashboard, Simulation tab (orange line falling)

> "Getting started is the hardest part of work, and reminders stop working.
> The same reminder every day works at first, then you tune it out. In our simulation it falls from about 60% to about a third.
> Agents like Muse can book your flight, but nobody can open your essay for you.
> So we built **Momentum**: a personal agent that learns which nudges actually get *you* to start."

## Scene 2: Momentum calls you (0:20 – 1:30), the wow moment
**Screen:** Momentum Phone tab. **Telegram:** send `/call`

> "Momentum doesn't wait in a chat window. It calls me. This page simulates a real phone call."

- **It rings → click Accept.** Momentum speaks (Claude wrote the line, AssemblyAI is the voice).
- **Say:** *"Ugh, not now, I'm exhausted."*
  > "It heard 'exhausted', so next time it'll ask for something smaller, not push harder."
- **Wait ~15 s or send `/call` →** a smaller nudge (tiny step / 5-minute timer). Accept.
- **Say:** *"I'll do it in a while."* → it says *"Sure, I'll check back in 5 minutes."*
  > "That's not a no, so it doesn't count against that nudge. And it keeps its promise."
- **~10 s later it rings again:** *"…it's Momentum again, like I promised."* Accept.
- **Say:** *"Okay fine, I'll start."* → a warm, varied reply. Done.
  > "(For the demo, one minute runs in two seconds.)"

## Scene 3: It explains itself (1:30 – 1:50)
**Screen:** dashboard → **Live** tab → Person: you (show the "Why this one" column), or send `/why` in Telegram

> "Every decision is logged with its reason, like 'you said you were tired, and a tiny step suits that'.
> Everything lives in **SingleStore** and every decision goes to **Amplitude**."

## Scene 4: What it learns about one person (1:50 – 2:20)
**Screen:** Live tab → Person: **Maya (demo, simulated)** → report at the top

> "This is Maya, a *simulated* user with four weeks of history. Momentum tried 13 kinds of nudges.
> Mornings: a tiny step, working alongside her, or a reward gets her going. Evenings: a deadline.
> Streaks, 'proud of you' and gentle check-ins never worked on her, so Momentum retired them.
> It now only uses what actually moves Maya, and still rotates between those so they don't wear off."

## Scene 5: Does it work over time? (2:20 – 2:50)
**Screen:** Simulation tab → Night Owl Student → point at the lines and the 4 cards

> "We simulated 60 days with four synthetic people.
> Orange: the same reminder wears off. Green: Momentum gets *better* every week, about 58% up to 76%.
> Blue is a strategy that cheats by knowing the answers. Momentum reaches about 82% of it.
> Here the night owl's deadlines stop working on day 30. Watch Momentum dip, then adapt."

## Scene 6: We stress-tested it (2:50 – 3:15)
**Screen:** README Firedrill tables on GitHub (or the Firedrill web app → Simulations)

> "We drilled Momentum in **Firedrill** against synthetic users.
> An exhausted student: it told them their *team* was counting on them. There was no team. 52 → fixed → 95.
> A stubborn student said 'not opening it', and Momentum celebrated. 57 → fixed → 92.
> Firedrill found bugs we'd never have caught ourselves."

## Scene 7: Stack + close (3:15 – 3:35)
**Screen:** back to Momentum Phone

> "Claude writes every nudge. AssemblyAI handles voice in and out. SingleStore holds state, Amplitude tracks every decision, Firedrill tests it.
> Real phone calls through Twilio are built too.
> **Momentum: the nudge that learns what moves you.**"

**Stop recording.**

---

## After recording
1. Trim if needed, upload to **YouTube (Unlisted)** or **Loom**, copy the link.
2. Open **tokensand.com/personalagenthack/submit**.
3. Paste from **`SUBMISSION.md`**, add the video link and team names/emails.
4. Repo: **https://github.com/rishabshukla-code/momentum**

## If something goes wrong on camera
| Problem | Fix |
|---|---|
| Phone page doesn't ring | Reload tab → Turn on Momentum Phone → `/call` |
| `/call` says "set a task first" | `/task Hackathon pitch \| today 5pm`, then `/call` |
| No sound | Unmute the Edge tab; click "Turn on Momentum Phone" again |
| Mic not heard | 🔒 in the address bar → Microphone: Allow → reload (tap buttons work too) |
