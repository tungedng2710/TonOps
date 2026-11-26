#!/bin/sh
set -eu

action=$1
repo=$2
expected_commit=${3:-}
export TMPDIR=/tmp
tmp=$(mktemp -d /tmp/mlflow-git.XXXXXX)
trap 'rm -rf "$tmp"' EXIT
url=http://gitea:3000
user=mlops-admin

cat >"$tmp/askpass" <<'ASKPASS'
#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' mlops-admin ;;
  *Password*) cat /run/secrets/git_admin_password ;;
esac
ASKPASS
chmod 700 "$tmp/askpass"
export GIT_ASKPASS="$tmp/askpass" GIT_TERMINAL_PROMPT=0

if [ "$action" = write ]; then
  printf 'user = "%s:%s"\n' "$user" "$(cat /run/secrets/git_admin_password)" | \
    curl --config - --max-time 15 --fail --silent --show-error \
    --header 'Content-Type: application/json' \
    --data "{\"name\":\"$repo\",\"private\":true}" "$url/api/v1/user/repos" > /dev/null
  git init -q -b main "$tmp/source"
  printf '%s\n' "MLflow core Git fixture $repo" >"$tmp/source/README.md"
  git -C "$tmp/source" add README.md
  git -C "$tmp/source" -c user.name='MLflow Integration' -c user.email=integration@example.invalid \
    commit -qm 'Add core integration fixture'
  git -C "$tmp/source" push -q "$url/$user/$repo.git" main
  expected_commit=$(git -C "$tmp/source" rev-parse HEAD)
fi

if GIT_ASKPASS=/bin/false git ls-remote "$url/$user/$repo.git" >/dev/null 2>&1; then
  echo 'Unauthenticated Git access unexpectedly succeeded' >&2
  exit 1
fi
git clone -q --branch main "$url/$user/$repo.git" "$tmp/checkout"
actual_commit=$(git -C "$tmp/checkout" rev-parse HEAD)
[ "$actual_commit" = "$expected_commit" ]
[ "$(cat "$tmp/checkout/README.md")" = "MLflow core Git fixture $repo" ]
printf '%s\n' "$actual_commit"
