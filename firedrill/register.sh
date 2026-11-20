#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "## register"
firedrill register --descriptor descriptor.json --name "Momentum" --session-only --json
echo "## persona"
firedrill library save --kind persona --file persona_tired.json --session-only --json
echo "## evaluation"
firedrill library save --kind evaluation --file evaluation_nudging.json --session-only --json
