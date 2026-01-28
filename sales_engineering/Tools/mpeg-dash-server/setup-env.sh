#!/usr/bin/env bash
# Cross-platform environment setup for macOS and WSL2 Ubuntu
# - Creates Python venv, installs deps, sets env vars
# - Optional: start backend and/or UI

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS_NAME="$(uname -s)"
IS_WSL=0
if [[ "$OS_NAME" == "Linux" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL=1
fi

PY_BIN="python3"
PIP_BIN="pip"
VENVDIR="${ROOT_DIR}/.venv"
MEDIA_ROOT_DEFAULT="${ROOT_DIR}/media"
BACKEND_URL_DEFAULT="http://localhost:8000"
DASH_ROOT_DEFAULT="${MEDIA_ROOT_DEFAULT}/dash"
PUBLIC_HTTPS_ORIGIN_DEFAULT="https://clarifai-lab.ddns.net:5443"
MEDIA_ROOT="${MEDIA_ROOT:-$MEDIA_ROOT_DEFAULT}"
DASH_ROOT="${DASH_ROOT:-$DASH_ROOT_DEFAULT}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
HTTPS_PORT="${HTTPS_PORT:-5443}"
TLS_DOMAIN="${TLS_DOMAIN:-}"
TLS_EMAIL="${TLS_EMAIL:-}"
PUBLIC_HTTPS_ORIGIN="${PUBLIC_HTTPS_ORIGIN:-$PUBLIC_HTTPS_ORIGIN_DEFAULT}"
UI_BASIC_AUTH="${UI_BASIC_AUTH:-0}"
UI_BASIC_AUTH_REALM="${UI_BASIC_AUTH_REALM:-Restricted}"
UI_BASIC_AUTH_FILE="${UI_BASIC_AUTH_FILE:-/etc/nginx/.htpasswd-mpeg-dash}"
START_BACKEND=0
START_UI=0
SETUP_NGINX=0
LETSENSCRIPT_PATH="${LETSENSCRIPT_PATH:-$ROOT_DIR/letsenscript.sh}"

usage() {
  cat <<EOF
Usage: $0 [options]
  --start-backend          Launch uvicorn once setup completes
  --start-ui               Launch Streamlit UI once setup completes
  --setup-nginx            Install + configure nginx reverse proxy on port ${HTTPS_PORT}
  --tls-domain <domain>    Domain for Let's Encrypt/letsenscript issuance
  --tls-email <email>      Contact email for certificate issuance
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-backend)
      START_BACKEND=1
      shift
      ;;
    --start-ui)
      START_UI=1
      shift
      ;;
    --setup-nginx)
      SETUP_NGINX=1
      shift
      ;;
    --tls-domain)
      [[ $# -lt 2 ]] && echo "--tls-domain requires a value" && exit 1
      TLS_DOMAIN="$2"
      shift 2
      ;;
    --tls-domain=*)
      TLS_DOMAIN="${1#*=}"
      shift
      ;;
    --tls-email)
      [[ $# -lt 2 ]] && echo "--tls-email requires a value" && exit 1
      TLS_EMAIL="$2"
      shift 2
      ;;
    --tls-email=*)
      TLS_EMAIL="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      exit 1
      ;;
  esac
done

ensure_python() {
  if ! command -v "$PY_BIN" >/dev/null 2>&1; then
    echo "python3 not found."
    if [[ "$OS_NAME" == "Darwin" ]]; then
      echo "Install via Homebrew: brew install python"
      exit 1
    else
      echo "Install via apt: sudo apt-get update && sudo apt-get install -y python3"
      exit 1
    fi
  fi
}

ensure_venv_module() {
  if ! "$PY_BIN" -m venv --help >/dev/null 2>&1; then
    echo "python venv module missing."
    if [[ "$OS_NAME" == "Linux" ]]; then
      if command -v apt-get >/dev/null 2>&1; then
        echo "Installing python3-venv via apt..."
        sudo apt-get update && sudo apt-get install -y python3-venv
      else
        echo "Please install python venv support for your distro."
        exit 1
      fi
    else
      echo "On macOS, ensure Python3 includes venv (brew python)."
      exit 1
    fi
  fi
}

ensure_ffmpeg() {
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg already installed: $(command -v ffmpeg)"
    return 0
  fi
  echo "ffmpeg not found; attempting to install it..."
  if [[ "$OS_NAME" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      echo "Installing ffmpeg via Homebrew (may prompt for password)..."
      brew install ffmpeg
    else
      echo "Homebrew not found. Please install Homebrew from https://brew.sh and run: brew install ffmpeg" >&2
      exit 1
    fi
  elif [[ "$OS_NAME" == "Linux" ]] && [[ "$IS_WSL" -eq 1 ]] && command -v apt-get >/dev/null 2>&1; then
    echo "Installing ffmpeg via apt (may prompt for sudo password)..."
    sudo apt-get update && sudo apt-get install -y ffmpeg
  else
    echo "Unsupported OS for automatic ffmpeg install. Please install ffmpeg manually and re-run this script." >&2
    exit 1
  fi

  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg install appears to have failed. Please install it manually and try again." >&2
    exit 1
  fi
}

ensure_nginx() {
  if command -v nginx >/dev/null 2>&1; then
    echo "nginx already installed: $(command -v nginx)"
    return 0
  fi
  echo "nginx not found; attempting to install it..."
  if [[ "$OS_NAME" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install nginx
    else
      echo "Homebrew is required to install nginx on macOS." >&2
      exit 1
    fi
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y nginx
  else
    echo "Unsupported platform for automated nginx install. Please install nginx manually." >&2
    exit 1
  fi
}

ensure_certbot() {
  if command -v certbot >/dev/null 2>&1; then
    echo "certbot available: $(command -v certbot)"
    return 0
  fi
  echo "certbot not found; installing..."
  if [[ "$OS_NAME" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install certbot
    else
      echo "Homebrew is required to install certbot on macOS." >&2
      exit 1
    fi
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y certbot
  else
    echo "Unsupported platform for automated certbot install. Please install certbot manually." >&2
    exit 1
  fi
}

run_letsenscript() {
  local domain="$1" email="$2"
  if [[ ! -x "$LETSENSCRIPT_PATH" ]]; then
    echo "letsenscript helper missing at $LETSENSCRIPT_PATH" >&2
    exit 1
  fi
  "$LETSENSCRIPT_PATH" "$domain" "$email"
}

determine_nginx_conf_target() {
  if [[ "$OS_NAME" == "Darwin" ]]; then
    if ! command -v brew >/dev/null 2>&1; then
      echo "Homebrew required to locate nginx config directories." >&2
      exit 1
    fi
    local prefix
    prefix="$(brew --prefix nginx 2>/dev/null || brew --prefix 2>/dev/null || echo "/usr/local")"
    if [[ -d "$prefix/etc/nginx/servers" ]]; then
      NGINX_CONF_TARGET="$prefix/etc/nginx/servers/mpeg_dash.conf"
      NGINX_CONF_SYMLINK=""
    else
      NGINX_CONF_TARGET="$prefix/etc/nginx/conf.d/mpeg_dash.conf"
      NGINX_CONF_SYMLINK=""
    fi
  else
    if [[ -d /etc/nginx/conf.d ]]; then
      NGINX_CONF_TARGET="/etc/nginx/conf.d/mpeg_dash.conf"
      NGINX_CONF_SYMLINK=""
    else
      NGINX_CONF_TARGET="/etc/nginx/sites-available/mpeg_dash.conf"
      NGINX_CONF_SYMLINK="/etc/nginx/sites-enabled/mpeg_dash.conf"
    fi
  fi
}

write_nginx_conf() {
  local backend_port="${BACKEND_PORT:-8000}"
  local ui_port="${UI_PORT:-8501}"
  local dash_root="${DASH_ROOT:-$DASH_ROOT_DEFAULT}"
  mkdir -p "$dash_root"
  determine_nginx_conf_target
  local conf_dir shell_link_dir
  conf_dir="$(dirname "$NGINX_CONF_TARGET")"
  sudo mkdir -p "$conf_dir"
  if [[ -n "$NGINX_CONF_SYMLINK" ]]; then
    shell_link_dir="$(dirname "$NGINX_CONF_SYMLINK")"
    sudo mkdir -p "$shell_link_dir"
  fi
  sudo tee "$NGINX_CONF_TARGET" >/dev/null <<EOF
server {
    listen ${HTTPS_PORT} ssl;
    server_name ${TLS_DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${TLS_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${TLS_DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    client_max_body_size 2g;
$( if [[ "$UI_BASIC_AUTH" == "1" ]]; then
  printf '    auth_basic "%s";\n    auth_basic_user_file %s;\n' "$UI_BASIC_AUTH_REALM" "$UI_BASIC_AUTH_FILE"
fi )

    # Health + API (FastAPI backend)
    location /api/ {
        proxy_pass http://127.0.0.1:${backend_port}/api/;
      proxy_set_header Host \$host;
      proxy_set_header X-Real-IP \$remote_addr;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /video {
        proxy_pass http://127.0.0.1:${backend_port}/video;
      proxy_set_header Host \$host;
      proxy_set_header X-Real-IP \$remote_addr;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_request_buffering off;
    }

    location /dash/ {
        alias ${dash_root}/;
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods 'GET, HEAD, OPTIONS';
        add_header Access-Control-Allow-Headers '*';
        expires 1m;
    }

    # Streamlit UI (with WebSocket support)
    location / {
        proxy_pass http://127.0.0.1:${ui_port}/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
      proxy_set_header Host \$host;
      proxy_set_header X-Real-IP \$remote_addr;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 86400;
    }
}
EOF
  if [[ -n "$NGINX_CONF_SYMLINK" ]]; then
    sudo ln -sf "$NGINX_CONF_TARGET" "$NGINX_CONF_SYMLINK"
  fi
  echo "nginx config written to $NGINX_CONF_TARGET"
}

test_nginx_conf() {
  sudo nginx -t
}

reload_nginx_service() {
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q nginx.service; then
    sudo systemctl enable --now nginx >/dev/null 2>&1 || true
    sudo systemctl reload nginx
    return
  fi
  if command -v service >/dev/null 2>&1 && service nginx status >/dev/null 2>&1; then
    sudo service nginx reload || sudo service nginx start
    return
  fi
  if command -v brew >/dev/null 2>&1; then
    if brew services list >/dev/null 2>&1; then
      brew services start nginx >/dev/null 2>&1 || true
      brew services restart nginx >/dev/null 2>&1 || sudo nginx -s reload || sudo nginx
      return
    fi
  fi
  sudo nginx -s reload || sudo nginx
}

setup_nginx_stack() {
  if [[ -z "$TLS_DOMAIN" || -z "$TLS_EMAIL" ]]; then
    cat <<EOF >&2
TLS_DOMAIN and TLS_EMAIL must be provided (either environment variables or --tls-domain/--tls-email flags)
to configure HTTPS with nginx.
EOF
    exit 1
  fi
  ensure_nginx
  ensure_certbot
  run_letsenscript "$TLS_DOMAIN" "$TLS_EMAIL"
  write_nginx_conf
  test_nginx_conf
  reload_nginx_service
  echo "nginx reverse proxy available at https://${TLS_DOMAIN}:${HTTPS_PORT}"
  if [[ -n "$PUBLIC_HTTPS_ORIGIN" ]]; then
    echo "Preferred HTTPS endpoint: $PUBLIC_HTTPS_ORIGIN"
  fi
}

create_venv() {
  if [[ ! -d "$VENVDIR" ]]; then
    echo "Creating venv at $VENVDIR"
    "$PY_BIN" -m venv "$VENVDIR"
  fi
  # shellcheck disable=SC1091
  source "$VENVDIR/bin/activate"
  PIP_BIN="pip"
}

install_deps() {
  echo "Installing Python deps..."
  "$PIP_BIN" install --upgrade pip
  "$PIP_BIN" install -r "$ROOT_DIR/requirements.txt"
}

write_env() {
  local envfile="$ROOT_DIR/.env"
  echo "Writing $envfile"
  cat > "$envfile" <<EOF
MEDIA_ROOT="$MEDIA_ROOT_DEFAULT"
BACKEND_URL="$BACKEND_URL_DEFAULT"
HTTPS_PORT="$HTTPS_PORT"
PUBLIC_HTTPS_ORIGIN="$PUBLIC_HTTPS_ORIGIN"
EOF
  mkdir -p "$MEDIA_ROOT_DEFAULT"
  echo "Created media root at $MEDIA_ROOT_DEFAULT"
}

start_backend() {
  echo "Starting backend (uvicorn)"
  MEDIA_ROOT="$MEDIA_ROOT_DEFAULT" uvicorn backend.main:app --host 0.0.0.0 --port 8000
}

start_ui() {
  echo "Starting Streamlit UI"
  MEDIA_ROOT="$MEDIA_ROOT_DEFAULT" BACKEND_URL="$BACKEND_URL_DEFAULT" streamlit run "$ROOT_DIR/ui/streamlit_app.py"
}

print_summary() {
  echo "\nSetup complete. Next steps:"
  echo "1) Activate venv: source $VENVDIR/bin/activate"
  echo "2) Start backend: MEDIA_ROOT=\"$MEDIA_ROOT_DEFAULT\" uvicorn backend.main:app --host 0.0.0.0 --port 8000"
  echo "3) Start UI: MEDIA_ROOT=\"$MEDIA_ROOT_DEFAULT\" BACKEND_URL=\"$BACKEND_URL_DEFAULT\" streamlit run ui/streamlit_app.py"
  if [[ -n "$PUBLIC_HTTPS_ORIGIN" ]]; then
    echo "4) Public HTTPS endpoint: $PUBLIC_HTTPS_ORIGIN"
  fi
}

# Main
ensure_python
ensure_venv_module
ensure_ffmpeg
ensure_certbot
create_venv
install_deps
write_env

if [[ "$SETUP_NGINX" -eq 1 ]]; then
  setup_nginx_stack
fi

if [[ "$START_BACKEND" -eq 1 ]]; then
  start_backend
fi
if [[ "$START_UI" -eq 1 ]]; then
  start_ui
fi

print_summary
