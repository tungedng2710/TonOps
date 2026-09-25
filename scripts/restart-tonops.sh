#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
WEB_DIR="${WORKSPACE_DIR}/clearml-web"
SERVER_DIR="${WORKSPACE_DIR}/clearml-server"
CONDA_ENV="${TONOPS_CONDA_ENV:-tungn197}"
SKIP_BUILD=false
RECREATE=true

usage() {
  cat <<'EOF'
Usage: scripts/restart-tonops.sh [options]

Build the TonOps UI, recreate the complete local service stack, and verify it.

Options:
  --skip-build    Restart without rebuilding the web application.
  --no-recreate   Restart existing containers instead of recreating them.
  -h, --help      Show this help message.

Environment:
  TONOPS_CONDA_ENV                 Conda environment (default: tungn197)
  CLEARML_IAM_ENABLED             Local IAM switch (default: true)
  CLEARML_IAM_SELF_SIGNUP_ENABLED Public signup switch (default: true)
EOF
}

while (($#)); do
  case "$1" in
    --skip-build)
      SKIP_BUILD=true
      ;;
    --no-recreate)
      RECREATE=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

for directory in "$WEB_DIR" "$SERVER_DIR"; do
  if [[ ! -d "$directory" ]]; then
    echo "Required directory not found: $directory" >&2
    exit 1
  fi
done

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but was not found in PATH" >&2
  exit 1
fi

eval "$(conda shell.bash hook)"
conda activate "$CONDA_ENV"

for command in docker corepack curl; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "$command is required but was not found in PATH" >&2
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker is unavailable or the current user cannot access it" >&2
  exit 1
fi

COMPOSE=(
  docker compose
  -f "${SERVER_DIR}/docker/compose.yaml"
  -f "${SERVER_DIR}/docker/compose.iam-local.yaml"
)
SERVICES=(mongo redis elasticsearch fileserver apiserver async_delete webserver)

show_diagnostics() {
  local exit_code=$?
  if ((exit_code != 0)); then
    echo
    echo "TonOps restart failed. Current service state:" >&2
    "${COMPOSE[@]}" ps >&2 || true
    echo
    echo "Recent API and web logs:" >&2
    "${COMPOSE[@]}" logs --tail=80 apiserver webserver >&2 || true
  fi
  exit "$exit_code"
}
trap show_diagnostics EXIT

if [[ "$SKIP_BUILD" == false ]]; then
  echo "Building TonOps web application..."
  (
    cd "$WEB_DIR"
    corepack pnpm run build
    corepack pnpm run build-widgets
  )
fi

# IAM stays enabled when Compose recreates the API container. Existing users and
# credentials remain in MongoDB; bootstrap secrets are only needed on first run.
export CLEARML_IAM_ENABLED="${CLEARML_IAM_ENABLED:-true}"
export CLEARML_IAM_SELF_SIGNUP_ENABLED="${CLEARML_IAM_SELF_SIGNUP_ENABLED:-true}"
# Compose parses the optional agent-services block even though this script does
# not launch it. Define its optional variables to keep restart output quiet.
export CLEARML_HOST_IP="${CLEARML_HOST_IP:-}"
export CLEARML_API_ACCESS_KEY="${CLEARML_API_ACCESS_KEY:-}"
export CLEARML_API_SECRET_KEY="${CLEARML_API_SECRET_KEY:-}"
export CLEARML_AGENT_GIT_USER="${CLEARML_AGENT_GIT_USER:-}"
export CLEARML_AGENT_GIT_PASS="${CLEARML_AGENT_GIT_PASS:-}"

echo "Restarting TonOps services..."
if [[ "$RECREATE" == true ]]; then
  "${COMPOSE[@]}" up -d --force-recreate "${SERVICES[@]}"
else
  "${COMPOSE[@]}" restart "${SERVICES[@]}"
fi

container_ids="$("${COMPOSE[@]}" ps -q "${SERVICES[@]}")"
if [[ -z "$container_ids" ]]; then
  echo "Compose did not return any TonOps containers" >&2
  exit 1
fi

echo "Waiting for containers to enter the running state..."
deadline=$((SECONDS + 180))
while ((SECONDS < deadline)); do
  all_running=true
  for service in "${SERVICES[@]}"; do
    container_id="$("${COMPOSE[@]}" ps -q "$service")"
    if [[ -z "$container_id" ]] || [[ "$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null || true)" != true ]]; then
      all_running=false
      break
    fi
  done
  [[ "$all_running" == true ]] && break
  sleep 2
done

if [[ "$all_running" != true ]]; then
  echo "One or more TonOps containers did not start within 180 seconds" >&2
  exit 1
fi

wait_for_url() {
  local name=$1
  local url=$2
  local timeout=${3:-180}
  local end=$((SECONDS + timeout))

  echo "Waiting for ${name}: ${url}"
  until curl --fail --silent --show-error --max-time 5 "$url" >/dev/null 2>&1; do
    if ((SECONDS >= end)); then
      echo "${name} did not become ready within ${timeout} seconds" >&2
      return 1
    fi
    sleep 3
  done
}

wait_for_url "API server" "http://127.0.0.1:7862/debug.ping"
wait_for_url "web application" "http://127.0.0.1:7861/"
wait_for_url "file server" "http://127.0.0.1:7863/"

echo
"${COMPOSE[@]}" ps
echo
echo "TonOps is ready:"
echo "  Web:   http://localhost:7861"
echo "  API:   http://localhost:7862"
echo "  Files: http://localhost:7863"

trap - EXIT
