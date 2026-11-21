# How Momentum uses each sponsor's product

Show-and-tell guide for sponsor booths and judges: what each product does inside Momentum,
where it lives in the code, and exactly what to open to prove it live.

| Sponsor | Status | Role in Momentum |
|---|---|---|
| **Firedrill** | ✅ live | Stress-tests the agent against synthetic users; two before/after drills |
| **SingleStore** | ✅ live | The agent's memory: every task, nudge, reason and outcome |
| **Amplitude** | ✅ live | Analytics on every agent decision and outcome |
| **AssemblyAI** | ✅ live | Voice in (speech-to-text) and voice out (natural TTS) on Momentum Phone |
| **Claude API** | ✅ live | Writes every nudge in the chosen style |
| Arcee | built, no credits | Alternative nudge writer slot |
| Cognee, Superlinked, Guild, Persona, Statsig | not used | — |

---

## 🔥 Firedrill: stress-testing the agent

**What it does for Momentum:** Synthetic users talk to Momentum through a JSON-lines bridge
and Firedrill scores each conversation against our rubrics. It found real bugs we then fixed.

| Scenario | First run | After fix | What it caught |
|---|---|---|---|
| Excuse, then start (tired student) | 52.75 | **95.75** | Ignored "exhausted" and invented a team that didn't exist |
| Never starts (stubborn student) | 57.5 | **92.25** | Read "not opening it" as a start and celebrated |

**Show it live:**
1. Open **app.firedrill.run** → workspace **Momentum** → **Simulations**: four campaigns, two per world.
2. Open the 52.75 run → the conversation shows *"Your team will be happy…"*. Then open the 95.75 run → *"Just open your essay draft. One sentence."*
3. Point at the **[audit] line** on every reply: Momentum reports its own decision (nudge type, reason, excuse) so the rubric can score *what it did*, not just what it said.

**In the code:** `momentum/drill_bridge.py` (jsonl-process.v1 driver), `firedrill/` (personas, rubrics, scenarios, worlds, local plan scripts).

**Say:** *"Firedrill let us drill, fix, and re-drill the same world. Two real bugs, two before/afters: 52 → 95 and 57 → 92. We also added a 'best possible' yardstick to our own simulator because of how Firedrill made us think about evals."*

---

## 🗄️ SingleStore: the agent's memory

**What it does for Momentum:** All state lives in a SingleStore Helios Starter cluster over TLS:
`users`, `tasks`, and `nudges` (every nudge with the type chosen, **why**, the outcome and the excuse).
The brain reads this history to decide the next nudge; the dashboard and Maya's report read it too.
Lesson learned: SingleStore auto-increment IDs are unique but not time-ordered, so Momentum orders by time.

**Show it live:** SingleStore portal → **Editor → SQL Editor** → database `db_rishab_868f5`, run:

```sql
-- What works on Maya (the agent's learned profile, straight from the table)
SELECT context, arm AS nudge_type, COUNT(*) AS tries,
       SUM(outcome = 'started') AS got_started,
       ROUND(100 * SUM(outcome = 'started') / COUNT(*)) AS success_pct
FROM nudges WHERE chat_id = 'demo-maya'
GROUP BY context, arm ORDER BY context, success_pct DESC;
```

```sql
-- The agent's latest live decisions, with its reasons
SELECT sent_at, arm, outcome, excuse, LEFT(reason, 80) AS why
FROM nudges WHERE chat_id <> 'demo-maya'
ORDER BY sent_at DESC LIMIT 10;
```

```sql
-- What people say when they don't start
SELECT excuse, COUNT(*) AS n FROM nudges
WHERE excuse IS NOT NULL GROUP BY excuse ORDER BY n DESC;
```

**Then:** send `/call`, answer the call, re-run the second query: the new row appears instantly.

**In the code:** `momentum/store.py` (tables, TLS, BIGINT ids, time ordering), `momentum/migrate.py` (copies local history across).

**Say:** *"SingleStore is the agent's live memory: state, decision and telemetry in one place. The learned profile you see on the dashboard is just a GROUP BY on this table."*

---

## 📊 Amplitude: analytics on every decision

**What it does for Momentum:** The official Python SDK sends two events per nudge, with user ID `tg_<chat>`:
- `nudge_sent`: `arm` (nudge type), `context`, `reason`, `writer` (claude/template), `channel` (web_phone/telegram), bandit `scores` and `fatigue`
- `nudge_outcome`: `outcome` (started / snoozed / deferred / ignored), `success`, `latency_s`

**Show it live:**
1. Amplitude → your project → **Users & Sessions / User Look-Up** → search `tg_` → the event stream of your live calls.
2. **Create → Chart → Segmentation:** event `nudge_outcome`, measure *totals*, **group by `arm`**, filter `success = true`: which nudge types work.
3. Send `/call`, answer, and watch the new events land within ~a minute.

**In the code:** `momentum/analytics.py` (shared client), `track()` in `momentum/integrations.py`, called from `momentum/agent.py`.

**Say:** *"Every decision the agent makes is an Amplitude event, including why it chose it and its internal scores, so we can analyse the agent like a product."*

---

## 🎙️ AssemblyAI: voice in and voice out

**What it does for Momentum:** On Momentum Phone (a simulated phone call):
- **Speech-to-text:** your spoken answer ("ugh, not now, I'm exhausted") is transcribed, then Momentum decides started / not now + excuse / later.
- **Text-to-speech:** every line Momentum says is spoken in the calm, steady `aai-audrey` voice via AssemblyAI streaming TTS, prefetched while the phone rings so there's no pause.

**Show it live:** `http://localhost:8000/phone` → Turn on → `/call` → Accept → answer out loud. The transcript appears on screen ("You: '…'") and in Telegram.

**In the code:** `transcribe()` and `speak()` in `momentum/integrations.py`, `momentum/webphone.py`, `momentum/phone.html`.

**Say:** *"AssemblyAI is both ears and voice. It hears the excuse, and it speaks Claude's nudge like a person calling you."*

---

## 🤖 Claude API: writes every nudge

**What it does for Momentum:** The brain picks the *kind* of nudge; Claude (Opus 5.5, low effort, official
Anthropic SDK) writes the actual line in that style, in Momentum's warm voice, using only facts given
(never invents deadlines or people), and uses the time of day and last excuse for tone only.
Templates take over on any error; server-side refusal fallback is on.

**Show it live:** each call's spoken line is fresh, e.g. *"Want company while you work on your hackathon pitch? I'll sit right here with you."* Dashboard Live tab shows the text next to the brain's reason.

**In the code:** `write_with_claude()` in `momentum/integrations.py`.

---

## Links
- Firedrill: https://app.firedrill.run · https://firedrill.run/hacker-docs
- SingleStore: https://portal.singlestore.com
- Amplitude: https://app.amplitude.com
- AssemblyAI: https://www.assemblyai.com/dashboard
- Repo: https://github.com/rishabshukla-code/momentum
