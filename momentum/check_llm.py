"""Check the Arcee (LLM) connection and preview one nudge of each type.

Run:  python -m momentum.check_llm
"""
import sys
import time

import httpx

from . import config
from .integrations import write_nudge
from .nudges import ARMS


def main() -> None:
    if not (config.LLM_BASE_URL and config.LLM_API_KEY):
        sys.exit("Set LLM_BASE_URL and LLM_API_KEY in .env first.")

    print(f"Endpoint: {config.LLM_BASE_URL}")
    try:
        r = httpx.get(config.LLM_BASE_URL.rstrip("/") + "/models",
                      headers={"Authorization": f"Bearer {config.LLM_API_KEY}"}, timeout=15)
        if r.status_code == 401:
            sys.exit("401: the API key was rejected. Re-copy it from the Arcee platform.")
        r.raise_for_status()
        ids = [m.get("id") for m in r.json().get("data", [])]
        print("Models your key can use:\n  " + "\n  ".join(ids or ["(none listed)"]))
    except httpx.HTTPError as e:
        print(f"Could not list models ({e}); trying a completion anyway.")
        ids = []

    if not config.LLM_MODEL:
        sys.exit("\nPick one of the models above and set LLM_MODEL in .env, then run this again.")
    if ids and config.LLM_MODEL not in ids:
        print(f"\nWarning: LLM_MODEL={config.LLM_MODEL} is not in the list above.")

    print(f"\nWriting one nudge of each type with {config.LLM_MODEL}:\n")
    llm_ok = 0
    for arm in ARMS:
        t0 = time.time()
        text, source = write_nudge(arm, "Hackathon pitch", "today 4:30pm", "afternoon",
                                   streak=3, excuse="tired")
        llm_ok += source == "llm"
        print(f"  [{source:8s} {time.time() - t0:4.1f}s] {text}")

    if llm_ok == len(ARMS):
        print("\nArcee is connected. The bot will use it automatically.")
    elif llm_ok:
        print("\nPartly working: some calls fell back to templates (see warnings above).")
    else:
        print("\nAll calls fell back to templates. Check the warnings above for the error.")


if __name__ == "__main__":
    main()
