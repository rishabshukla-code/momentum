#!/bin/bash
# Turn texts and evidence. Usage: drill_detail.sh <campaign> <drill> <turn-id>...
cd "$(dirname "$0")"
C="$1"; D="$2"; shift 2
show() { firedrill report "$@" --session-only --json | python3 -c '
import json, sys
for l in sys.stdin:
    l = l.strip()
    if l.startswith("{"):
        d = json.loads(l).get("data", {})
        d.pop("slot", None)
        print(json.dumps(d, indent=1, ensure_ascii=False)[:4000])'; }
for t in "$@"; do echo "######## turn $t"; show "$C" drill "$D" conversation "$t"; done
echo "######## evidence"; show "$C" drill "$D" evidence
