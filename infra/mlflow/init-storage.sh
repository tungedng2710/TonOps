#!/bin/sh
set -eu

root_key=$(printf '%s' "$RUSTFS_ACCESS_KEY" | jq -sRr @uri)
root_secret=$(printf '%s' "$RUSTFS_SECRET_KEY" | jq -sRr @uri)
export RC_HOST_core="http://$root_key:$root_secret@rustfs:9000"
export RC_CONFIG_DIR="$(mktemp -d)"
trap 'rm -rf "$RC_CONFIG_DIR"' EXIT
access_key=$(cat /run/secrets/artifact_key)

# Do not write credential-bearing CLI diagnostics into Compose logs.
run() {
  description=$1
  shift
  if ! timeout 20 rc "$@" >"$RC_CONFIG_DIR/output" 2>&1; then
    echo "RustFS bootstrap failed: $description" >&2
    exit 1
  fi
}

for bucket in mlflow-artifacts ml-datasets ml-exports; do
  run "create $bucket" bucket create "core/$bucket" --ignore-existing
  run "enforce private access on $bucket" bucket anonymous set private "core/$bucket"
done

run 'create artifact policy' admin policy create core mlflow-artifact-service /opt/mlops/artifact-policy.json
run 'list service users' admin user ls core --json
user=$(jq -c --arg key "$access_key" '.users[] | select(.accessKey == $key)' "$RC_CONFIG_DIR/output")
if [ -z "$user" ]; then
  run 'create artifact service user' admin user add core "$access_key" "$(cat /run/secrets/artifact_secret)"
  run 'attach artifact policy' admin policy attach core mlflow-artifact-service --user "$access_key"
elif ! printf '%s\n' "$user" | jq -e '.status == "enabled" and .memberOf == []' >/dev/null; then
  echo 'The existing RustFS artifact identity must be enabled and have no groups' >&2
  exit 1
elif printf '%s\n' "$user" | jq -e '.policies == []' >/dev/null; then
  run 'attach artifact policy' admin policy attach core mlflow-artifact-service --user "$access_key"
elif ! printf '%s\n' "$user" | jq -e '.policies == ["mlflow-artifact-service"]' >/dev/null; then
  echo 'The existing RustFS artifact identity has unexpected policies' >&2
  exit 1
fi
echo 'RustFS private buckets and scoped artifact identity are ready'
