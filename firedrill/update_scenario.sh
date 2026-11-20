#!/bin/bash
# Save a new scenario revision, point the world at it, then plan again.
# Usage: update_scenario.sh <scenario-expected-revision> <world-expected-revision>
set -e
cd "$(dirname "$0")"
SCN_RES=a4920f4e-d3e9-4b6f-ac4a-ad558b002cd3
WORLD=65bc7f92-de62-42a9-92c2-0eb5fe64fb1d
AGENT=95f9c953-f7ab-4e2e-ba01-da36a098ad54

firedrill library save "$SCN_RES" --kind scenario --file scenario_excuse_then_start.json \
  --expected-revision "$1" --session-only --json > /tmp/scn.json

python3 - <<'EOF'
import json
v = [json.loads(l) for l in open("/tmp/scn.json") if '"library_version"' in l][0]["data"]
print("scenario:", v["id"], "rev", v["revision"], "max_turns", v["definition"]["max_turns"])
w = json.load(open("world.json"))
w["resources"] = [{"origin": "native_library", "kind": "scenario", "id": v["id"],
                   "revision": v["revision"], "digest": v["digest"]}]
json.dump(w, open("world.json", "w"), indent=2)
EOF

firedrill world save --agent "$AGENT" --file world.json --world "$WORLD" \
  --expected-revision "$2" --session-only --json > /tmp/world.json
python3 -c 'import json; d=[json.loads(l) for l in open("/tmp/world.json") if "world_revision" in l][0]["data"]; print("world revision:", d["revision"])'

bash plan.sh
