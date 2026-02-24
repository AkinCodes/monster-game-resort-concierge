#!/bin/bash
KEY="6f2b8e3a9d1c4f5b2a8e7d9c1b0a3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0"
MSG="${1:-What amenities does Vampire Manor offer?}"
curl -s -X POST http://localhost:8000/chat \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"${MSG}\"}" | python3 -m json.tool
