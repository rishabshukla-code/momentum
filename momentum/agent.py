"""The agent loop: decide when to nudge, pick a type, send it, learn from the result.

tick() is the event trigger. The bot calls it every 30 seconds, and the HTTP
server exposes it at POST /trigger so a Guild cron or webhook can drive it
when the bot runs in a sandbox.
"""
from __future__ import annotations

import logging
from datetime import datetime

from . import brain, config, store, telegram
from .integrations import EXCUSE_BOOST, recall, remember, track, write_nudge

log = logging.getLogger("momentum")


def _quiet(now: datetime) -> bool:
    s, e = config.QUIET_START_HOUR, config.QUIET_END_HOUR
    h = now.hour
    return (s <= h or h < e) if s > e else (s <= h < e)


def send_nudge(chat_id: str) -> dict | None:
    task = store.active_task(chat_id)
    if not task:
        return None
    now = datetime.now()
    user = store.get_user(chat_id)
    last = store.last_nudge(chat_id)
    boost = dict(EXCUSE_BOOST.get(last["excuse"], {})) if last and last["excuse"] else {}
    streak = store.streak(chat_id)
    if streak < 2:
        boost["streak"] = -1.0  # a streak nudge needs an actual streak

    d = brain.choose(store.history(chat_id), now,
                     prior=brain.onboarding_prior(user and user["onboarding"]), boost=boost,
                     excuse=last["excuse"] if last else None)
    memories = recall(chat_id, f"What nudges work for this person in the {d.context}?")
    text, source = write_nudge(d.arm, task["title"], task["deadline"], d.context,
                               streak, last and last["excuse"], memories)

    nudge_id = store.log_nudge(chat_id, task["id"], d.arm, d.context, text, d.reason)
    msg = telegram.send(chat_id, text, buttons=[[
        ("✅ Started", f"started:{nudge_id}"), ("😴 Not now", f"snoozed:{nudge_id}"),
    ]])
    store.set_message_id(nudge_id, str(msg["message_id"]))
    track(chat_id, "nudge_sent", {
        "arm": d.arm, "context": d.context, "reason": d.reason, "writer": source,
        "scores": {k: round(v, 3) for k, v in d.scores.items()},
        "fatigue": {k: round(v, 3) for k, v in d.fatigue.items()},
    })
    log.info("nudge %s -> %s [%s] %s", nudge_id, chat_id, d.arm, d.reason)
    return {"nudge_id": nudge_id, "arm": d.arm, "reason": d.reason, "text": text}


def record_outcome(nudge_id: int, outcome: str) -> dict | None:
    row = store.resolve(nudge_id, outcome)
    if not row:
        return None
    chat_id = row["chat_id"]
    latency = (datetime.now() - row["sent_at"]).total_seconds()
    track(chat_id, "nudge_outcome", {
        "arm": row["arm"], "context": row["context"], "outcome": outcome,
        "success": outcome == "started", "latency_s": round(latency),
    })
    verb = "worked" if outcome == "started" else "did not work"
    remember(chat_id, f"On {row['sent_at']:%A} {row['context']}, a '{row['arm']}' nudge {verb}.")
    if outcome == "started":
        store.finish_task(chat_id)  # done nudging for this block
    return row


def tick() -> list[dict]:
    """One pass of the agent. Safe to call as often as you like."""
    for row in store.expire_waiting(config.RESPONSE_WINDOW_MIN):
        track(row["chat_id"], "nudge_outcome", {
            "arm": row["arm"], "context": row["context"], "outcome": "ignored", "success": False})
        remember(row["chat_id"], f"A '{row['arm']}' nudge in the {row['context']} was ignored.")
        if row.get("message_id"):
            telegram.clear_buttons(row["chat_id"], row["message_id"])

    sent = []
    now = datetime.now()
    if _quiet(now):
        return sent
    for user in store.all_users():
        chat_id = user["chat_id"]
        task = store.active_task(chat_id)
        if not task:
            continue
        last = store.last_nudge(chat_id)
        if last and last["task_id"] == task["id"]:
            if last["outcome"] is None:
                continue  # still waiting for a reply
            if (now - last["sent_at"]).total_seconds() < config.NUDGE_GAP_MIN * 60:
                continue
        if store.nudges_for_task(task["id"]) >= config.MAX_NUDGES_PER_BLOCK:
            continue
        r = send_nudge(chat_id)
        if r:
            sent.append(r)
    return sent
