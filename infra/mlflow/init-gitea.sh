#!/bin/sh
set -eu

git_admin=mlops-admin
git_password=$(cat /run/secrets/git_admin_password)
gitea() {
  /app/gitea/gitea --config /etc/gitea/app.ini "$@"
}

users=$(gitea admin user list --admin)
if ! printf '%s\n' "$users" | awk -v name="$git_admin" '$2 == name {found=1} END {exit !found}'; then
  if ! gitea admin user create --username "$git_admin" --password "$git_password" \
    --email mlops-admin@example.invalid --admin --must-change-password=false >/dev/null 2>&1; then
    echo 'Gitea bootstrap failed to create the local administrator' >&2
    exit 1
  fi
fi

if ! printf 'user = "%s:%s"\n' "$git_admin" "$git_password" | \
  curl --config - --fail --silent --show-error --max-time 10 --output /dev/null http://gitea:3000/api/v1/user; then
  echo 'Gitea bootstrap could not authenticate the generated local administrator' >&2
  exit 1
fi
echo 'Gitea local administrator is ready'
