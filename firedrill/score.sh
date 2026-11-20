#!/bin/bash
# Score and conversation for a campaign's first drill. Usage: score.sh <campaign-id>
cd "$(dirname "$0")"
C="$1"
for i in $(seq 1 12); do
  firedrill report "$C" --session-only --json > /tmp/rep.json
  python3 - <<'EOF' && break
import json, sys
d = json.loads(open("/tmp/rep.json").readline())["data"]
ev = list(d.get("evaluations", {}).values())
rep = ev[0].get("report") if ev else None
if not rep or rep.get("pending"):
    sys.exit(1)
print("status:", rep["status"], "| score:", rep["mean_criterion_score"], "| met:", rep["criteria_met"], "/", rep["criteria_total"])
open("/tmp/drill_id", "w").write(d["slots"][0]["drill_id"])
EOF
  echo "waiting for scoring..."; sleep 10
done
D=$(cat /tmp/drill_id)
firedrill report "$C" drill "$D" conversation --session-only --json | python3 -c '
import json, sys
d = json.loads(sys.stdin.readline())["data"]
print(" ".join(t["action_id"] for t in d["turns"]["results"]))' > /tmp/turns
for t in $(cat /tmp/turns); do
  firedrill report "$C" drill "$D" conversation "$t" --session-only --json | python3 -c '
import json, sys
t = json.loads(sys.stdin.readline())["data"]["turn"]
print("USER :", t["participant_text"]); print("AGENT:", t["target_text"].replace("\n", " / ")); print()'
done
