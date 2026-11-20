"""HTTP trigger so Momentum acts on events, not chat turns.

Point a Guild cron / webhook (or any scheduler) at POST /trigger.
Run:  uvicorn momentum.server:app --port 8000
"""
from fastapi import FastAPI, Header, HTTPException

from . import agent, config, store

app = FastAPI(title="Momentum")
store.init_db()


@app.post("/trigger")
def trigger(x_trigger_token: str = Header(default="")):
    if x_trigger_token != config.TRIGGER_TOKEN:
        raise HTTPException(401, "bad token")
    return {"sent": agent.tick()}


@app.get("/recent")
def recent(limit: int = 20):
    return store.recent_nudges(limit)


@app.get("/health")
def health():
    return {"ok": True}
