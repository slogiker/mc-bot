#!/bin/bash
# Minimal Playit Tunnel Creation Test

# Load secret key
if [ -f "data/playit_secret.key" ]; then
    SECRET_KEY=$(cat data/playit_secret.key)
    echo "Found Secret Key."
else
    echo "Error: data/playit_secret.key not found."
    exit 1
fi

# 1. Get Agent Run Data (to get Agent ID)
echo "Fetching Agent ID..."
AGENT_DATA=$(curl -s -X POST \
    -H "authorization: Agent-Key ${SECRET_KEY}" \
    -H "content-type: application/json" \
    -d '{}' \
    https://api.playit.gg/v1/agents/rundata)

AGENT_ID=$(echo "$AGENT_DATA" | jq -r '.data.agent_id' 2>/dev/null)

if [ -z "$AGENT_ID" ] || [ "$AGENT_ID" = "null" ]; then
    echo "Failed to get Agent ID."
    echo "Full Response: $AGENT_DATA"
    exit 1
fi

echo "Agent ID: $AGENT_ID"

# 2. Try to create tunnel
echo "Attempting to create tunnel..."
TUNNEL_RESULT=$(curl -s -X POST \
    -H "authorization: Agent-Key ${SECRET_KEY}" \
    -H "content-type: application/json" \
    -d "{
  \"name\": \"minecraft-test\",
  \"tunnel_type\": \"minecraft-java\",
  \"port_type\": \"both\",
  \"port_count\": 1,
  \"origin\": {
    \"type\": \"agent\",
    \"data\": {
      \"agent_id\": \"${AGENT_ID}\",
      \"local_ip\": \"127.0.0.1\",
      \"local_port\": 25565
    }
  },
  \"enabled\": true
}" https://api.playit.gg/v1/tunnels/create)

echo "--- API RESPONSE ---"
echo "$TUNNEL_RESULT" | jq .
echo "--------------------"

if echo "$TUNNEL_RESULT" | grep -q '"status":"success"'; then
    echo "SUCCESS: Tunnel created!"
else
    echo "FAILED: See error above."
fi
