#!/bin/bash
# Load .env if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
KEY="${MRC_API_KEY:-your-api-key-here}"
MSG="${1:-What amenities does Vampire Manor offer?}"
SID="${2:-}"

if [ -z "$SID" ]; then
  BODY="{\"message\": \"${MSG}\"}"
else
  BODY="{\"message\": \"${MSG}\", \"session_id\": \"${SID}\"}"
fi

curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY" | python3 -m json.tool
