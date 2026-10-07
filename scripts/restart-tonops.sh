#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_BUILD=false
RECREATE=false

usage() {
  cat <<'EOF'
Usage: scripts/restart-tonops.sh [--skip-build] [--force-recreate]

Build the local Docker image, start the Compose stack, and wait for readiness.
  --skip-build    Use the existing local image.
  --force-recreate   Recreate all containers, including data services.
EOF
}

while (($#)); do
  case "$1" in
    --skip-build) SKIP_BUILD=true ;;
    --force-recreate) RECREATE=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
  shift
done

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env and create the bootstrap password file." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is unavailable or the current user cannot access it." >&2
  exit 1
fi

# RustFS runs as uid 10001 and needs a writable bind mount.
rustfs_data_root="${RUSTFS_DATA_ROOT:-}"
if [[ -z "$rustfs_data_root" ]]; then
  rustfs_data_root="$(sed -n 's/^RUSTFS_DATA_ROOT=//p' .env | tail -1)"
fi
if [[ -z "$rustfs_data_root" ]]; then
  echo "Set RUSTFS_DATA_ROOT in .env before starting the stack." >&2
  exit 1
fi
mkdir -p "$rustfs_data_root"
if [[ "$(stat -c %u "$rustfs_data_root")" != 10001 ]]; then
  chown 10001:10001 "$rustfs_data_root"
fi

if [[ "$SKIP_BUILD" == false ]]; then
  docker compose build apiserver
fi

COMPOSE_ARGS=(up -d)
if [[ "$RECREATE" == true ]]; then
  COMPOSE_ARGS+=(--force-recreate)
fi
docker compose "${COMPOSE_ARGS[@]}" gitea rustfs rustfs_init mongo redis elasticsearch apiserver fileserver webserver async_delete

wait_for_url() {
  local label=$1
  local url=$2
  local deadline=$((SECONDS + 180))
  until curl --fail --silent --show-error --max-time 5 "$url" >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then
      echo "$label did not become ready within 180 seconds." >&2
      docker compose ps >&2
      docker compose logs --tail=80 apiserver fileserver webserver gitea >&2
      return 1
    fi
    sleep 3
  done
}

api_port="$(docker compose port apiserver 8008 | sed 's/.*://')"
web_port="$(docker compose port webserver 80 | sed 's/.*://')"
files_port="$(docker compose port fileserver 8081 | sed 's/.*://')"
rustfs_port="$(docker compose port rustfs 9000 | sed 's/.*://')"
gitea_port="$(docker compose port gitea 3000 | sed 's/.*://')"
wait_for_url "API server" "http://127.0.0.1:${api_port}/debug.ping"
wait_for_url "web app" "http://127.0.0.1:${web_port}/"
wait_for_url "fileserver" "http://127.0.0.1:${files_port}/"
wait_for_url "RustFS" "http://127.0.0.1:${rustfs_port}/health"
wait_for_url "Gitea" "http://127.0.0.1:${gitea_port}/"
docker compose ps
