#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT="${SCRIPT_DIR}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --no-recreate          skip dropping/creating the database (only bring up the container)
  --compose-file <path>  point to a custom podman-compose file (defaults to podman-compose.yaml)
    --schema-file <path>   SQL file to apply after ensuring the database exists (defaults to create-schema.sql)
  -h, --help             show this help message
EOF
    exit 1
}

require_command() {
    if ! command -v "$1" &>/dev/null; then
        print_error "Required command '$1' is missing; please install it and re-run."
        exit 1
    fi
}

load_dotenv() {
    local env_file="${PROJECT_ROOT}/.env"
    if [ -f "${env_file}" ]; then
        print_info "Loading environment variables from .env"
        # shellcheck disable=SC1090
        set -a
        # shellcheck disable=SC1091
        source "${env_file}"
        set +a
    fi
}

wait_for_postgres() {
    local deadline=$((SECONDS + WAIT_TIMEOUT))
    print_info "Waiting for Postgres to accept connections inside ${DB_CONTAINER} (timeout ${WAIT_TIMEOUT}s)"
    while true; do
        if podman exec -e PGPASSWORD="${DB_PASSWORD}" "${DB_CONTAINER}" pg_isready -U "${DB_USER}" &>/dev/null; then
            print_success "Postgres inside ${DB_CONTAINER} is ready"
            break
        fi
        if [ ${SECONDS} -ge ${deadline} ]; then
            print_error "Postgres did not become ready before timeout"
            exit 1
        fi
        sleep ${WAIT_INTERVAL}
    done
}

recreate_database() {
    print_info "Dropping database '${DB_NAME}' (if it exists)"
    podman exec -e PGPASSWORD="${DB_PASSWORD}" "${DB_CONTAINER}" \
        psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"

    print_info "Creating database '${DB_NAME}'"
    podman exec -e PGPASSWORD="${DB_PASSWORD}" "${DB_CONTAINER}" \
        psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${DB_NAME};"

    print_success "Database '${DB_NAME}' ready inside ${DB_CONTAINER}"
}

apply_schema() {
    if [ -z "${SCHEMA_FILE}" ]; then
        print_warning "No schema file specified; skipping schema application."
        return
    fi
    if [ ! -f "${SCHEMA_FILE}" ]; then
        print_error "Schema file not found at ${SCHEMA_FILE}"
        exit 1
    fi
    print_info "Applying database schema from ${SCHEMA_FILE}"
    if podman exec -i -e PGPASSWORD="${DB_PASSWORD}" "${DB_CONTAINER}" \
        psql -U "${DB_USER}" -d "${DB_NAME}" < "${SCHEMA_FILE}"; then
        print_success "Schema applied successfully"
    else
        print_error "Failed to apply schema from ${SCHEMA_FILE}"
        exit 1
    fi
}

# Default configuration values (can be overridden via .env or environment)
COMPOSE_FILE="podman-compose.yaml"
RECREATE_DB=true
WAIT_INTERVAL=2
WAIT_TIMEOUT=60
DB_USER="videologo_user"
DB_PASSWORD="videologo_pass"
DB_NAME="videologo_db"
DB_CONTAINER="videologo_db"
DB_SERVICE="db"
DB_PORT="35432"
SCHEMA_FILE="create-schema.sql"

if [ $# -gt 0 ]; then
    while [ $# -gt 0 ]; do
        case "$1" in
            --no-recreate)
                RECREATE_DB=false
                shift
                ;;
            --compose-file)
                if [ $# -lt 2 ]; then
                    print_error "--compose-file requires a path argument"
                    usage
                fi
                COMPOSE_FILE="$2"
                shift 2
                ;;
            --schema-file)
                if [ $# -lt 2 ]; then
                    print_error "--schema-file requires a path argument"
                    usage
                fi
                SCHEMA_FILE="$2"
                shift 2
                ;;
            -h|--help)
                usage
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                ;;
        esac
    done
fi

require_command podman
require_command podman-compose

cd "${PROJECT_ROOT}"
load_dotenv

# Allow .env or exported envs to override defaults
DB_USER="${DB_USER:-videologo_user}"
DB_PASSWORD="${DB_PASSWORD:-videologo_pass}"
DB_NAME="${DB_NAME:-videologo_db}"
DB_CONTAINER="${DB_CONTAINER:-videologo_db}"
DB_SERVICE="${DB_SERVICE:-db}"
DB_PORT="${DB_PORT:-35432}"

if [[ "${COMPOSE_FILE}" != /* ]]; then
    COMPOSE_FILE="${PROJECT_ROOT}/${COMPOSE_FILE}"
fi

if [[ -n "${SCHEMA_FILE}" && "${SCHEMA_FILE}" != /* ]]; then
    SCHEMA_FILE="${PROJECT_ROOT}/${SCHEMA_FILE}"
fi

if [ ! -f "${COMPOSE_FILE}" ]; then
    print_error "podman-compose file not found at ${COMPOSE_FILE}"
    exit 1
fi

print_info "Ensuring database container '${DB_CONTAINER}' is running via ${COMPOSE_FILE}"
podman-compose -f "${COMPOSE_FILE}" up -d "${DB_SERVICE}"

wait_for_postgres

if [ "${RECREATE_DB}" = true ]; then
    recreate_database
else
    print_warning "Skipping drop/create; existing database '${DB_NAME}' is left untouched."
fi

apply_schema

print_success "Database initialization complete"
print_info "Connect to localhost:${DB_PORT} with ${DB_USER}/${DB_PASSWORD}"
