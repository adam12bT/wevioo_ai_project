#!/bin/bash
set -e

echo "================================================================"
echo "Starting AnythingLLM (lightweight fork) on Hugging Face Spaces"
echo "================================================================"
echo "DEBUG: raw VECTOR_DB env value = [${VECTOR_DB}]"
echo "DEBUG: is VECTOR_DB set at all? $( [ -z "${VECTOR_DB+x}" ] && echo 'NO - unset' || echo 'YES - set' )"
env | grep -i "vector\|qdrant\|chroma" | sed 's/=.*/=<redacted-if-key>/' || echo "DEBUG: no VECTOR/QDRANT/CHROMA env vars found at all"

# --- 1. Start Chroma vector DB server in the background (Chroma only) ---
# /data/chroma is ephemeral on free HF Spaces (no Persistent Storage add-on) —
# it survives container sleep/wake, but is WIPED on every rebuild (e.g. any
# git push to the Space, or a manual "Factory reboot"). See the deploy notes
# for how to add real persistence if you need it.
#
# If VECTOR_DB is set to something else (e.g. "qdrant", pointed at Qdrant
# Cloud), skip this entirely — no point running an unused Chroma server on
# the free tier's limited CPU/RAM.
CHROMA_PID=""
if [ "${VECTOR_DB:-chroma}" = "chroma" ]; then
  CHROMA_DATA_DIR="${CHROMA_DATA_DIR:-/data/chroma}"
  mkdir -p "$CHROMA_DATA_DIR"
  chroma run --host 0.0.0.0 --port 8000 --path "$CHROMA_DATA_DIR" &
  CHROMA_PID=$!

  echo "Waiting for Chroma to come up on :8000..."
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1 || \
       curl -sf http://localhost:8000/api/v2/heartbeat > /dev/null 2>&1; then
      echo "Chroma is up."
      break
    fi
    sleep 1
  done
else
  echo "VECTOR_DB=${VECTOR_DB} — skipping bundled Chroma server."
fi

# --- 2. Migrate/generate Prisma client + run the actual app ---
{
  cd /app/server/ &&
    export CHECKPOINT_DISABLE=1 &&
    npx prisma generate --schema=./prisma/schema.prisma &&
    npx prisma migrate deploy --schema=./prisma/schema.prisma &&
    node /app/server/index.js
} &
SERVER_PID=$!

{ node /app/collector/index.js; } &
COLLECTOR_PID=$!

# If any of the running processes dies, bring the whole container down so
# HF Spaces shows it as crashed/restarting rather than silently half-broken.
WATCH_PIDS="$SERVER_PID $COLLECTOR_PID"
[ -n "$CHROMA_PID" ] && WATCH_PIDS="$CHROMA_PID $WATCH_PIDS"
wait -n $WATCH_PIDS
exit $?