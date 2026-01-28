#!/usr/bin/env bash
# Lightweight helper that wraps certbot/Let's Encrypt issuance so other scripts
# can request certificates without re-implementing the CLI plumbing.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <domain> <email> [extra certbot args...]" >&2
  exit 1
fi

DOMAIN="$1"
EMAIL="$2"
shift 2

CERTBOT_BIN="${CERTBOT_BIN:-certbot}"
HTTP_PORT="${LETSENSCRIPT_HTTP_PORT:-80}"

if ! command -v "$CERTBOT_BIN" >/dev/null 2>&1; then
  echo "Error: $CERTBOT_BIN is not available on PATH. Install certbot before running letsenscript." >&2
  exit 1
fi

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
EXTRA_CERTBOT_ARGS=()
if [[ $# -gt 0 ]]; then
  EXTRA_CERTBOT_ARGS=("$@")
fi

if [[ "$HTTP_PORT" != "80" ]]; then
  echo "Note: HTTP-01 challenge will bind to port ${HTTP_PORT}. Ensure this port is reachable." >&2
fi

run_certbot() {
  local subcommand="$1"
  shift
  local cmd=(sudo "$CERTBOT_BIN" "$subcommand" "$@")
  if [[ ${#EXTRA_CERTBOT_ARGS[@]} -gt 0 ]]; then
    cmd+=("${EXTRA_CERTBOT_ARGS[@]}")
  fi
  "${cmd[@]}"
}

if sudo test -f "${CERT_DIR}/fullchain.pem" && sudo test -f "${CERT_DIR}/privkey.pem"; then
  echo "Existing certificate detected for ${DOMAIN}. Attempting renewal..."
  sudo "$CERTBOT_BIN" renew \
    --cert-name "$DOMAIN" \
    --force-renewal \
    --standalone \
    --preferred-challenges http \
    --http-01-port "$HTTP_PORT" \
    "${EXTRA_CERTBOT_ARGS[@]+${EXTRA_CERTBOT_ARGS[@]}}"
else
  echo "Requesting Let's Encrypt certificate for ${DOMAIN} via standalone challenge..."
  run_certbot renew \
    --cert-name "$DOMAIN" \
    --force-renewal \
    --standalone \
    --preferred-challenges http \
    --http-01-port "$HTTP_PORT"
    -d "$DOMAIN" \
    "${EXTRA_CERTBOT_ARGS[@]+${EXTRA_CERTBOT_ARGS[@]}}"
fi
  run_certbot certonly \
    --standalone \
    --preferred-challenges http \
    --http-01-port "$HTTP_PORT" \
    --agree-tos \
    --no-eff-email \
    -m "$EMAIL" \
    -d "$DOMAIN"
