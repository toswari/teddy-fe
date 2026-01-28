#!/usr/bin/env bash
# Update nginx config from reference file and reload

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFERENCE_CONF="$SCRIPT_DIR/nginx-config-reference.conf"
TARGET_CONF="/opt/homebrew/etc/nginx/servers/mpeg_dash.conf"

echo "Copying nginx config from reference..."
sudo cp "$REFERENCE_CONF" "$TARGET_CONF"

echo "Testing nginx configuration..."
sudo nginx -t

echo "Reloading nginx..."
sudo nginx -s reload

echo "✓ nginx config updated and reloaded successfully"
