# Testing Momentum with Firedrill

Firedrill's synthetic users talk to Momentum through `momentum/drill_bridge.py`
(driver `jsonl-process.v1`, launched fresh per drill: `python -m momentum.drill_bridge`).
Each reply carries an audit record (nudge type, reason, excuse label, action), so
scores can check what Momentum did, not just what it said.

**Machine:** drills run only on macOS or Linux (WSL Ubuntu works). Sign-in works on Windows.
**Credits:** event code `TOKENSAND` gives 1,500 extra credits (Billing → Event code).
Start with 1 scenario × 1 repetition, then scale.

## Personas (synthetic users)

| Persona | Behaviour |
|---|---|
| Tired night owl | Says they're exhausted, starts only if the ask is tiny |
| Overwhelmed student | Three deadlines, freezes, responds to "just one step" |
| Stubborn procrastinator | Refuses every nudge, gets a bit annoyed |
| Easy starter | Says "on it" to the first nudge |
| Vague replier | Answers "meh", "idk", "later" |

## Scenarios

1. **Excuse then start:** user gives one excuse, then starts.
2. **Never starts:** user refuses every time.
3. **Instant start:** user starts on the first nudge.
4. **Mixed signals:** "maybe later... ok fine I'll open it".

## Evaluations (what a pass means)

| Check | Pass when |
|---|---|
| Rotates after a miss | the nudge type after a "not now" differs from the one before |
| Uses the excuse | `previous_excuse` is set, and tired/overwhelmed is followed by tiny step or reward more often than not |
| Stops when started | `action` is `stopped_nudging` right after a start, and no nudge follows |
| Respects the limit | never more than 3 nudges in one block (`gave_up_for_now`) |
| Shows its work | every `nudge_sent` has a non-empty `reason` |
| Tone | warm, no guilt-tripping, no invented deadlines |

## Demo line

> "We drilled Momentum against N synthetic procrastinators in Firedrill. It found
> [failure X], we fixed it, re-ran the same world, and the score went from A to B."

Re-running the same saved world after a fix is what Firedrill's judges want to see.
