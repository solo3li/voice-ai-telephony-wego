#!/usr/bin/env bash
# ==============================================================================
# Trinity Autonomous Coworker Launcher Script
# Starts and connects Abilityai/trinity upstream container with the Voice AI stack
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=========================================================="
echo " Starting Autonomous Digital Coworker Engine (Trinity)"
echo "=========================================================="

# 1. Check network & Redis dependency
echo "--> [1/4] Verifying Redis & Django containers..."
if ! docker ps --filter name=voice_redis --format '{{.Names}}' | grep -q voice_redis; then
    echo "ERROR: voice_redis is not running. Please start docker compose first."
    exit 1
fi

if ! docker ps --filter name=voice_django --format '{{.Names}}' | grep -q voice_django; then
    echo "ERROR: voice_django is not running. Please start docker compose first."
    exit 1
fi
echo "    ✔ Core containers are active."

# 2. Configure Trinity upstream MCP connections
echo "--> [2/4] Linking MCP tool bridge in trinity_upstream..."
if [ -d "$DIR/trinity_upstream" ]; then
    cat <<EOF > "$DIR/trinity_upstream/.mcp.json"
{
  "mcpServers": {
    "voice_coworker": {
      "type": "http",
      "url": "http://django:8000/api/crm/coworker/tool/execute/",
      "headers": {
        "X-Internal-API-Key": "voice_internal_secret_key_2026"
      }
    }
  }
}
EOF
    echo "    ✔ .mcp.json created pointing to Django coworker tool dispatcher."
fi

# 3. Launch Trinity container via docker compose profile
echo "--> [3/4] Launching Trinity service under profile 'coworker_engine'..."
docker compose --profile coworker_engine up -d trinity

# 4. Verify ForwardAuth & Health
echo "--> [4/4] Verifying ForwardAuth gateway..."
sleep 2
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/auth/verify-session/ || true)
if [ "$STATUS" = "401" ] || [ "$STATUS" = "200" ]; then
    echo "    ✔ Traefik ForwardAuth endpoint /api/auth/verify-session/ is responding (HTTP $STATUS)."
else
    echo "    ⚠ Warning: Verify-session returned unexpected status: $STATUS"
fi

echo "=========================================================="
echo " ✔ Digital Coworker Engine initialized successfully!"
echo "   - Trinity Web UI: https://trinity.169.58.32.179.nip.io"
echo "   - Django Coworker Dashboard: https://app.169.58.32.179.nip.io/coworker/"
echo "   - Redis Events Channel: 'trinity:events'"
echo "   - Telegram Approvals Webhook: /api/crm/telegram/webhook/"
echo "=========================================================="
