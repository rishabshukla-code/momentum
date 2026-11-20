#!/bin/bash
# Print a campaign's conversation and per-criterion results. Usage: report.sh <campaign-id>
cd "$(dirname "$0")"
C="$1"
firedrill report "$C" --session-only --json > /tmp/report.json
python3 - "$C" <<'EOF'
import json, subprocess, sys
c = sys.argv[1]
rows = [json.loads(l) for l in open("/tmp/report.json")]
drills = []
for r in rows:
    d = r.get("data", {})
    print("##", r.get("type"), json.dumps({k: d.get(k) for k in ("state", "portal_url", "url", "summary") if k in d})[:400])
    for dr in d.get("drills", []) or []:
        drills.append(dr.get("id") or dr.get("drill_id"))
def cmd(*a):
    out = subprocess.run(["firedrill", "report", c, *a, "--session-only", "--json"],
                         capture_output=True, text=True).stdout
    return [json.loads(l) for l in out.splitlines() if l.strip().startswith("{")]
for did in filter(None, drills):
    print("\n=== drill", did)
    for r in cmd("drill", did, "conversation"):
        print(json.dumps(r.get("data"), ensure_ascii=False)[:3000])
    print("\n--- results")
    for r in cmd("drill", did, "results"):
        print(json.dumps(r.get("data"), ensure_ascii=False)[:4000])
EOF
