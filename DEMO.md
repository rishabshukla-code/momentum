# Momentum: 3-minute demo script

**Setup before you go on stage**
- `.env` has `DEMO_MODE=true` (all timers become 1 minute).
- Terminal 1: `python -m momentum.bot`. Terminal 2: `streamlit run dashboard.py`.
- Phone screen mirrored to the projector (or Telegram Desktop next to the dashboard).
- Fresh chat already did `/start` and picked an onboarding answer.
- Backup video recorded before 4:00 PM.

---

### 1. Hook (20s)
> "I need nudges to get work done. But the same nudge stops working after a few days.
> Every reminder app, and even Meta's Muse, sends the same reminder forever.
> Muse can book your flight. It can't make you open your essay."

### 2. Live loop on the phone (70s)
1. Type `/task Hackathon pitch | today 4:30pm`, then `/nudge`.
2. A nudge arrives. Tap **😴 Not now**. When it asks what's in the way, type **"honestly too tired"**.
   > "A small task-specific model just classified that as *tired*. No big LLM needed."
3. Send `/nudge` again. It switches type, usually to a tiny step or a reward.
4. Send `/why`.
   > "It shows its reasoning: the nudge that usually works was used recently, so it rotated."
5. Tap **✅ Started**. It stops nudging.
6. Switch to the dashboard's **Live** tab: every decision, the reason, and the result.

### 3. The month in 30 seconds (50s)
Dashboard, **Simulated month** tab.
> "This only matters over weeks, so we simulated 30 days against synthetic users."
- Point at the orange line: "The same reminder starts at about 60% and wears off to 26%."
- Green line: "Momentum holds around 75%, and needs fewer pings to get you started."
- Heatmap: "And it learned *this* person: small steps work in the morning. Deadline nudges
  worked at night until day 15, then stopped, and Momentum moved on."

### 3b. Firedrill before/after (20s)
> "We drilled Momentum against a synthetic exhausted student in Firedrill. First run: 52.
> It ignored 'I'm exhausted' and told them their *team* was counting on them. There was no team.
> We fixed it, re-ran the same world: 95. Now 'exhausted' gets 'just open the doc, one sentence.'"

### 4. How it's built (25s)
> "It acts on its own trigger, not a chat turn. It needs the least access possible: one
> Telegram chat, no inbox. A small Arcee open model writes each nudge cheaply. Every
> decision and outcome lives in SingleStore and goes to Amplitude. Cognee remembers what
> works for you."
(Only name the partners you actually wired up.)

### 5. Close (15s)
> "Momentum: a personal agent that experiments on one person, and gets better at getting
> you moving."

---

**Likely judge questions**
- *Why not just random rotation?* Rotation alone beats a fixed reminder by a lot (that's the
  insight). Momentum adds a few points on top and fewer pings, and it adapts when what works
  for you changes (night-owl persona, day 15).
- *How do you know they really started?* Today it's the button plus the 15-minute window.
  Next: a desktop signal (doc or IDE opened) for an automatic, honest check.
- *Privacy?* It only sees your replies to it. No inbox, calendar, or screen access.
