#!/bin/bash
# Run an applied campaign's drills on this machine. Usage: run.sh <campaign-id>
cd "$(dirname "$0")"
firedrill run --plan local-plan.json --descriptor descriptor.json --campaign "$1" \
  --approve --session-only --enroll-device --json 2>&1 | tee /tmp/run.json | cut -c1-300
