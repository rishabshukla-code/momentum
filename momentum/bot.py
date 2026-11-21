"""Telegram bot: receives taps and messages, and runs the agent tick on a timer.

Run:  python -m momentum.bot
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from . import agent, brain, config, events, store, telegram, voice
from .integrations import build_memory, classify_excuse
from .nudges import NUDGE_TYPES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("momentum")
logging.getLogger("httpx").setLevel(logging.WARNING)  # its request logs include the bot token

HELP = (
    "☕ I'm Momentum. I nudge you to start your work, and I learn which nudges actually "
    "work on you.\n\n"
    "/task Essay draft | Friday 5pm  - set what to work on (deadline optional)\n"
    "/nudge  - nudge me right now\n"
    "/why    - why I picked my last nudge\n"
    "/stats  - what I've learned about you\n"
    "/add Mom's birthday Nov 20  - save an event; I pick the category and when to call\n"
    "/events - your saved events and when I'll call next\n"
    "/remove <id> - delete a saved event\n"
    "/phone  - get nudges as calls on Momentum Phone (simulated call)\n"
    "/call   - call me with a nudge right now\n"
    "/done   - stop nudging for now"
)

ONBOARD_Q = "One quick question so I can start smart: what usually gets you moving?"
ONBOARD_OPTS = [("⏰ Deadlines", "onb:deadlines"), ("🪜 Small steps", "onb:small steps"),
                ("🤝 Someone counting on me", "onb:someone counting"), ("🍪 Rewards", "onb:rewards")]

awaiting_excuse: dict[str, int] = {}  # chat_id -> nudge_id we asked "what's in the way?" about


def handle_message(msg: dict) -> None:
    chat_id = str(msg["chat"]["id"])
    text = (msg.get("text") or "").strip()
    store.upsert_user(chat_id, msg["chat"].get("first_name", ""))

    if text.startswith("/start"):
        telegram.send(chat_id, HELP)
        telegram.send(chat_id, ONBOARD_Q, buttons=[ONBOARD_OPTS[:2], ONBOARD_OPTS[2:]])
    elif text.startswith("/task"):
        body = text[len("/task"):].strip()
        if not body:
            telegram.send(chat_id, "Tell me the task, e.g. /task Essay draft | Friday 5pm")
            return
        title, _, deadline = (p.strip() for p in body.partition("|"))
        store.add_task(chat_id, title, deadline or None)
        telegram.send(chat_id, f"Got it: {title}" + (f" (due {deadline})" if deadline else "")
                      + ". I'll nudge you. Send /nudge if you want one now.")
    elif text.startswith("/nudge"):
        if not store.active_task(chat_id):
            telegram.send(chat_id, "Set a task first with /task.")
        else:
            agent.send_nudge(chat_id)
    elif text.startswith("/why"):
        last = store.last_nudge(chat_id)
        telegram.send(chat_id, f"🧠 {last['reason']}" if last else "No nudges yet.")
    elif text.startswith("/stats"):
        telegram.send(chat_id, stats_text(chat_id))
        build_memory(chat_id)
    elif text.startswith("/add"):
        body = text[len("/add"):].strip()
        if not body:
            telegram.send(chat_id, "Tell me the event, e.g. /add Mom's birthday Nov 20, or "
                          "/add Stats midterm Dec 12, or /add Take vitamins every morning")
            return
        ev = events.add(chat_id, body)
        nxt = events.next_call(ev)
        when = f"{nxt:%a %b} {nxt.day} at {nxt:%H:%M}" if nxt else "nothing scheduled"
        if nxt and nxt.year != datetime.now().year:
            when += f" {nxt.year}"
        due_now = [k for e, k, _ in events.due() if e["id"] == ev["id"]]
        telegram.send(chat_id, f"Saved (id {ev['id']}):\n{events.describe(ev)}\nNext call: "
                      + ("right now 📞" if due_now else when))
    elif text.startswith("/events"):
        mine = events.for_chat(chat_id)
        if not mine:
            telegram.send(chat_id, "No saved events yet. Try /add Mom's birthday Nov 20")
        else:
            lines = []
            for ev in mine:
                nxt = events.next_call(ev)
                lines.append(f"[{ev['id']}] {events.describe(ev)}\n      next call: "
                             + (f"{nxt:%a %b} {nxt.day} {nxt.year} {nxt:%H:%M}" if nxt else "none"))
            telegram.send(chat_id, "\n\n".join(lines))
    elif text.startswith("/remove"):
        ev = events.remove(chat_id, text[len("/remove"):].strip())
        telegram.send(chat_id, f"Removed: {ev['title']}" if ev else "No event with that id. See /events")
    elif text.startswith("/phone"):
        if "off" in text.lower():
            voice.set_call(chat_id, False)
            telegram.send(chat_id, "Okay, back to messages here.")
        elif not config.PUBLIC_BASE_URL:
            telegram.send(chat_id, "Momentum Phone needs the server's public link (PUBLIC_BASE_URL).")
        else:
            voice.set_call(chat_id, "web")
            telegram.send(chat_id, "📞 Momentum Phone is on. Open this on your phone and tap "
                          f"'Turn on Momentum Phone':\n{config.PUBLIC_BASE_URL}/phone?k={config.TRIGGER_TOKEN}"
                          "\nThen send /call, or just wait for me to call.")
    elif text.startswith("/callme"):
        on = "off" not in text.lower()
        if on and not voice.ready():
            telegram.send(chat_id, "Phone calls aren't set up yet (Twilio settings missing).")
            return
        voice.set_call(chat_id, on)
        telegram.send(chat_id, "📞 Got it, I'll call you for nudges." if on
                      else "Okay, back to messages here.")
    elif text.startswith("/call"):
        if not store.active_task(chat_id):
            telegram.send(chat_id, "Set a task first with /task.")
        elif voice.call_mode(chat_id) == "web":
            agent.send_nudge(chat_id)  # rings Momentum Phone
        elif voice.ready():
            voice.set_call(chat_id, True)
            agent.send_nudge(chat_id)
        else:
            telegram.send(chat_id, "Turn on Momentum Phone first with /phone.")
    elif text.startswith("/done"):
        store.finish_task(chat_id)
        telegram.send(chat_id, "Okay, I'll stay quiet. Proud of you either way. ☕")
    elif chat_id in awaiting_excuse:
        nudge_id = awaiting_excuse.pop(chat_id)
        label, source = classify_excuse(text)
        store.set_excuse(nudge_id, label)
        telegram.send(chat_id, f"Got it, sounds like '{label}'. I'll keep that in mind next time.")
        log.info("excuse %s via %s", label, source)
    else:
        telegram.send(chat_id, HELP)


def handle_callback(cb: dict) -> None:
    chat_id = str(cb["message"]["chat"]["id"])
    data = cb.get("data", "")
    action, _, value = data.partition(":")

    if action == "onb":
        store.set_onboarding(chat_id, value)
        telegram.answer_callback(cb["id"], "Thanks!")
        telegram.clear_buttons(chat_id, cb["message"]["message_id"],
                               f"{ONBOARD_Q}\n→ {value}. Now tell me what to work on with /task.")
        return

    if action in ("started", "snoozed"):
        row = agent.record_outcome(int(value), action)
        if not row:
            telegram.answer_callback(cb["id"], "Already counted")
            return
        old = cb["message"].get("text", "")
        if action == "started":
            telegram.answer_callback(cb["id"], "Yay!")
            telegram.clear_buttons(chat_id, cb["message"]["message_id"], old + "\n\n✅ Started")
            telegram.send(chat_id, "Love that. Go go go. 🔥")
        else:
            telegram.answer_callback(cb["id"], "Okay")
            telegram.clear_buttons(chat_id, cb["message"]["message_id"], old + "\n\n😴 Not now")
            awaiting_excuse[chat_id] = int(value)
            telegram.send(chat_id, "No worries. What's getting in the way? (one line is fine)")


def stats_text(chat_id: str) -> str:
    hist = store.history(chat_id)
    if not hist:
        return "I haven't learned anything yet. Give me a few nudges first."
    now = datetime.now()
    ctx = brain.context_for(now)
    table = brain.win_rate_table(hist, now)[ctx]
    lines = [f"🧠 What works on you in the {ctx.replace('_', ' ')}:"]
    for arm, rate in sorted(table.items(), key=lambda x: -x[1]):
        tries = sum(1 for o in hist if o.arm == arm)
        lines.append(f"{NUDGE_TYPES[arm]['emoji']} {NUDGE_TYPES[arm]['label']}: "
                     f"{rate:.0%}  ({tries} tries)")
    wins = sum(o.success for o in hist)
    lines.append(f"\nOverall: {wins}/{len(hist)} nudges got you started.")
    return "\n".join(lines)


def main() -> None:
    store.init_db()
    me = telegram.call("getMe")
    log.info("Momentum running as @%s (demo mode: %s)", me["username"], config.DEMO_MODE)
    offset, last_tick = None, 0.0
    while True:
        try:
            for u in telegram.get_updates(offset, timeout=1 if config.FAST_CLOCK else (10 if config.DEMO_MODE else 20)):
                offset = u["update_id"] + 1
                try:
                    if "message" in u:
                        handle_message(u["message"])
                    elif "callback_query" in u:
                        handle_callback(u["callback_query"])
                except Exception:
                    log.exception("failed to handle update")
            if time.time() - last_tick > (2 if config.FAST_CLOCK else 30):
                agent.tick()
                last_tick = time.time()
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("loop error, retrying in 3s")
            time.sleep(3)


if __name__ == "__main__":
    main()
