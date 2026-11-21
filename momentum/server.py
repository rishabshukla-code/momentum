"""HTTP server: event trigger + phone-call webhooks.

Point a Guild cron / webhook (or any scheduler) at POST /trigger.
Twilio calls /voice/twiml and /voice/reply during a phone nudge (see voice.py).
Run:  uvicorn momentum.server:app --port 8000
"""
from fastapi import FastAPI, Header, HTTPException

from . import agent, config, planner, store, voice, webphone

app = FastAPI(title="Momentum")
app.include_router(voice.router)
app.include_router(webphone.router)
app.include_router(planner.router)
store.init_db()


@app.post("/trigger")
def trigger(x_trigger_token: str = Header(default="")):
    if x_trigger_token != config.TRIGGER_TOKEN:
        raise HTTPException(401, "bad token")
    return {"sent": agent.tick()}


@app.get("/recent")
def recent(limit: int = 20, x_trigger_token: str = Header(default="")):
    if x_trigger_token != config.TRIGGER_TOKEN:  # private data; the server may be public
        raise HTTPException(401, "bad token")
    return store.recent_nudges(limit)


@app.get("/health")
def health():
    return {"ok": True}
