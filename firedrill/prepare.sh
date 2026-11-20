#!/bin/bash
# Fill in the machine-specific hashes for the descriptor (run inside WSL/Linux from the repo root).
set -e
cd "$(dirname "$0")/.."
ROOT_ID=$(node -e 'const c=require("crypto"),f=require("fs");const p=f.realpathSync(process.argv[1]);const s=f.statSync(p,{bigint:true});console.log(c.createHash("sha256").update("firedrill.root-identity.v1\0").update(p).update("\0").update(`${s.dev}:${s.ino}`).digest("hex"))' .)
ADAPTER=$(sha256sum momentum/drill_bridge.py | cut -d' ' -f1)
sed -e "s/__ROOT_ID__/$ROOT_ID/" -e "s/__ADAPTER_SHA__/$ADAPTER/" firedrill/descriptor.template.json > firedrill/descriptor.json
echo "root=$ROOT_ID"
echo "adapter=$ADAPTER"
echo "path=$(realpath .)"
