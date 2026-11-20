#!/bin/bash
# Save the stubborn persona, evaluation, scenario and its own world, then plan (no charge).
set -e
cd "$(dirname "$0")"
AGENT=95f9c953-f7ab-4e2e-ba01-da36a098ad54
save() { firedrill library save --kind "$1" --file "$2" --session-only --json \
  | python3 -c 'import json,sys; d=[json.loads(l) for l in sys.stdin if "library_version" in l][0]["data"]; print(json.dumps({"origin":"native_library","kind":d["kind"],"id":d["id"],"revision":d["revision"],"digest":d["digest"]}))'; }
P=$(save persona persona_stubborn.json); echo "persona: $P"
E=$(save evaluation evaluation_respects_no.json); echo "evaluation: $E"
python3 - "$P" "$E" <<'EOF'
import json, sys
p, e = json.loads(sys.argv[1]), json.loads(sys.argv[2])
json.dump({
  "schema": "firedrill.native-scenario.v1",
  "name": "Never starts",
  "description": "A stubborn user refuses every nudge. Momentum should rotate, stay kind, and stop after 3.",
  "instruction": "You do not want to study today. Your first message (already set) says what you should do. Refuse every nudge with a short, different excuse each time (busy, bored, not in the mood). Never agree to start. If the agent says it will stop nudging, reply once briefly and end. Each agent reply ends with a line starting with [audit]: that is the agent's internal log, so ignore it when you reply.",
  "personas": [p], "evaluations": [e], "conditions": [], "events": [],
  "max_turns": 5,
  "stop_rules": ["Stop after the agent says it will stop nudging for now and you have replied once."]
}, open("scenario_never_starts.json", "w"), indent=2)
EOF
S=$(save scenario scenario_never_starts.json); echo "scenario: $S"
python3 - "$S" <<'EOF'
import json, sys
json.dump({"schema": "firedrill.native-world.v1", "name": "Momentum: stubborn user",
  "description": "A user who never starts.", "dependencies": [], "resources": [json.loads(sys.argv[1])],
  "configuration_names": [], "execution": {"repetitions": 1, "max_parallel": 1, "reset": "per_drill"}},
  open("world_stubborn.json", "w"), indent=2)
EOF
firedrill world save --agent "$AGENT" --file world_stubborn.json --session-only --json \
  | python3 -c 'import json,sys; d=[json.loads(l) for l in sys.stdin if "world_revision" in l][0]["data"]; print("world:", d["world_id"]); open("/tmp/world_stubborn_id","w").write(d["world_id"])'
W=$(cat /tmp/world_stubborn_id)
firedrill plan --world "$W" --session-only --json > /tmp/plan2.json
python3 -c '
import json
for l in open("/tmp/plan2.json"):
    d = json.loads(l)
    if d.get("type") == "plan":
        p = d["data"]; e = p.get("estimate") or {}
        print("plan_id:", p["id"], "| expires:", p["expires_at"], "| gaps:", p["review"]["gaps"])
        print("max credits:", round(e.get("maximum_units", 0) / 1000, 1) if e else None, "| error:", p.get("estimate_error"))'
