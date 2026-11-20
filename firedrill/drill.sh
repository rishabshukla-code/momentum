#!/bin/bash
# Show one drill's conversation and results. Usage: drill.sh <campaign-id> <drill-id>
cd "$(dirname "$0")"
for view in conversation results; do
  echo "######## $view"
  firedrill report "$1" drill "$2" "$view" --session-only --json | python3 -c '
import json, sys
for l in sys.stdin:
    l = l.strip()
    if l.startswith("{"):
        print(json.dumps(json.loads(l).get("data"), indent=1, ensure_ascii=False)[:6000])'
done
