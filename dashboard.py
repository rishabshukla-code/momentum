"""Momentum demo dashboard.

Run:  streamlit run dashboard.py
"""
import json
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from momentum import brain, store
from momentum.nudges import NUDGE_TYPES
from momentum.simulate import simulate

ROOT = Path(__file__).parent
st.set_page_config(page_title="Momentum", page_icon="☕", layout="wide")

STRAT_LABEL = {"fixed": "Same reminder every time", "random": "Random nudge",
               "momentum": "Momentum (learns)"}
STRAT_COLOR = {"Same reminder every time": "#c2410c", "Random nudge": "#a8a29e",
               "Momentum (learns)": "#15803d"}
ARM_LABEL = {a: f"{v['emoji']} {v['label']}" for a, v in NUDGE_TYPES.items()}

st.title("☕ Momentum")
st.caption("The nudge that learns what moves you.")

tab_sim, tab_live = st.tabs(["Simulated month", "Live from Telegram"])

# ------------------------------------------------------------------ simulation
with tab_sim:
    path = ROOT / "sim_results.json"
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("Re-run simulation"):
            with st.spinner("Simulating 30 days x 40 runs..."):
                path.write_text(json.dumps(simulate(30, 40, 7)))
    if not path.exists():
        path.write_text(json.dumps(simulate(30, 40, 7)))
    sim = json.loads(path.read_text())
    with c1:
        persona = st.selectbox("Synthetic user", list(sim["personas"]),
                               format_func=lambda p: p.replace("_", " ").title())
    res = sim["personas"][persona]
    st.write(f"*{res['description']}*")

    s = res["strategies"]
    k1, k2, k3 = st.columns(3)
    k1.metric("Got started (Momentum)", f"{s['momentum']['overall']:.0%}",
              f"{(s['momentum']['overall'] - s['fixed']['overall']) * 100:+.0f} pts vs same reminder")
    k2.metric("Pings per start", f"{s['momentum']['nudges_per_start']:.1f}",
              f"{s['momentum']['nudges_per_start'] - s['fixed']['nudges_per_start']:+.1f} vs same reminder",
              delta_color="inverse")
    k3.metric("Same reminder, last 5 days",
              f"{sum(s['fixed']['daily_start_rate'][-5:]) / 5:.0%}",
              f"down from {sum(s['fixed']['daily_start_rate'][:5]) / 5:.0%} in week 1",
              delta_color="off")

    rows = []
    for strat, v in s.items():
        series = pd.Series(v["daily_start_rate"]).rolling(3, min_periods=1).mean()
        rows += [{"Day": d + 1, "Started": r, "Strategy": STRAT_LABEL[strat]}
                 for d, r in enumerate(series)]
    df = pd.DataFrame(rows)
    st.subheader("Nudges wear off. Momentum notices.")
    st.altair_chart(
        alt.Chart(df).mark_line(strokeWidth=3).encode(
            x=alt.X("Day:Q"),
            y=alt.Y("Started:Q", axis=alt.Axis(format="%"), title="Work blocks started",
                    scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("Strategy:N", scale=alt.Scale(domain=list(STRAT_COLOR),
                                                          range=list(STRAT_COLOR.values()))),
            tooltip=["Day", alt.Tooltip("Started:Q", format=".0%"), "Strategy"],
        ).properties(height=320),
        width="stretch",
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Which nudge Momentum picked each day")
        picks = [{"Day": d + 1, "Nudge": ARM_LABEL[a], "Times": n}
                 for d, p in enumerate(s["momentum"]["picks_per_day"]) for a, n in p.items()]
        st.altair_chart(
            alt.Chart(pd.DataFrame(picks)).mark_area().encode(
                x="Day:Q", y=alt.Y("Times:Q", stack="normalize", axis=alt.Axis(format="%"),
                                   title="Share of nudges"),
                color=alt.Color("Nudge:N"), tooltip=["Day", "Nudge", "Times"],
            ).properties(height=280),
            width="stretch",
        )
    with right:
        st.subheader("What it learned about this person")
        learned = s["momentum"]["learned"]
        heat = [{"Time of day": ctx.replace("_", " "), "Nudge": ARM_LABEL[a], "Win rate": r}
                for ctx, arms in learned.items() if ctx in ("morning", "evening")
                for a, r in arms.items()]
        st.altair_chart(
            alt.Chart(pd.DataFrame(heat)).mark_rect().encode(
                x="Time of day:N", y="Nudge:N",
                color=alt.Color("Win rate:Q", scale=alt.Scale(scheme="greens"),
                                legend=alt.Legend(format="%")),
                tooltip=["Time of day", "Nudge", alt.Tooltip("Win rate:Q", format=".0%")],
            ).properties(height=280),
            width="stretch",
        )

# ------------------------------------------------------------------ live
with tab_live:
    store.init_db()
    st.button("Refresh")
    recent = store.recent_nudges(30)
    if not recent:
        st.info("No live nudges yet. Start the bot (python -m momentum.bot) and send /task.")
    else:
        hist = store.history()
        now = datetime.now()
        ctx = brain.context_for(now)
        table = brain.win_rate_table(hist, now)[ctx] if hist else {}
        wins = sum(o.success for o in hist)
        m1, m2, m3 = st.columns(3)
        m1.metric("Nudges sent", len(recent))
        m2.metric("Got you started", f"{wins}/{len(hist)}" if hist else "-")
        # only rank nudge types that have actually worked at least once (untried ones start at 50%)
        proven = {a: r for a, r in table.items() if any(o.arm == a and o.success for o in hist)}
        if proven:
            best = max(proven, key=proven.get)
            m3.metric("Best nudge so far", ARM_LABEL[best],
                      f"{sum(o.arm == best and o.success for o in hist)} start(s)", delta_color="off")
        else:
            m3.metric("Best nudge so far", "Still learning")
        st.subheader("Every decision, and why")
        icon = {"started": "✅ started", "snoozed": "😴 not now", "ignored": "🔕 ignored",
                None: "⏳ waiting"}
        st.dataframe(pd.DataFrame([{
            "Time": r["sent_at"].strftime("%H:%M:%S") if r["sent_at"] else "",
            "Nudge": ARM_LABEL.get(r["arm"], r["arm"]),
            "Message": r["text"],
            "Why this one": r["reason"],
            "Result": icon.get(r["outcome"], r["outcome"]),
            "Excuse": r["excuse"] or "",
        } for r in recent]), width="stretch", hide_index=True)
