#!/bin/bash
# Apply an approved plan. Usage: apply.sh <plan-id>
cd "$(dirname "$0")"
firedrill apply "$1" --approve --follow --session-only --json 2>&1 | tee /tmp/apply.json | cut -c1-400
