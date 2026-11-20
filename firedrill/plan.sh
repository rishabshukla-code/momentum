#!/bin/bash
# Effect-free plan review; prints the plan id, gaps and credit estimate.
cd "$(dirname "$0")"
# Usage: plan.sh [world-id]   (default: the "Excuse, then start" world)
firedrill plan --world "${1:-65bc7f92-de62-42a9-92c2-0eb5fe64fb1d}" --session-only --json > /tmp/plan.json
python3 - <<'EOF'
import json
for line in open("/tmp/plan.json"):
    d = json.loads(line)
    if d.get("type") == "plan":
        p = d["data"]
        print("plan_id:", p["id"])
        print("expires:", p["expires_at"])
        print("gaps:", p["review"]["gaps"])
        print("estimate:", json.dumps(p.get("estimate"), indent=1))
        print("estimate_error:", p.get("estimate_error"), "|", p.get("estimate_error_detail"))
    else:
        print(line.strip()[:500])
EOF
