#!/usr/bin/env bash
set -euo pipefail
URL="${1:?url required}"
TRIES="${2:-60}"
for i in $(seq 1 "$TRIES"); do
  if curl -fsS "$URL" >/dev/null; then
    echo "OK $URL"
    exit 0
  fi
  sleep 1
done
echo "Timeout waiting for $URL"
exit 1
