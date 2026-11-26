#!/bin/sh
set -eu

fixture=$1
case "$fixture" in
  ''|*[!a-z0-9-]*) echo 'Invalid policy fixture name' >&2; exit 1 ;;
esac
directory=$(mktemp -d)
root_key=$RUSTFS_ACCESS_KEY
root_secret=$RUSTFS_SECRET_KEY
encoded_key=$(printf '%s' "$root_key" | jq -sRr @uri)
encoded_secret=$(printf '%s' "$root_secret" | jq -sRr @uri)
export RC_HOST_core="http://$encoded_key:$encoded_secret@rustfs:9000"
export RC_CONFIG_DIR="$directory"
key_a=$(od -An -N10 -tx1 /dev/urandom | tr -d ' \n')
key_b=$(od -An -N10 -tx1 /dev/urandom | tr -d ' \n')
secret_a=$(od -An -N20 -tx1 /dev/urandom | tr -d ' \n')
secret_b=$(od -An -N20 -tx1 /dev/urandom | tr -d ' \n')
bucket=http://rustfs:9000/ml-datasets

rc_step() {
  description=$1
  shift
  if ! timeout 20 rc "$@" >"$directory/rc.log" 2>&1; then
    echo "RustFS policy fixture failed: $description" >&2
    return 1
  fi
}

s3_request() {
  access=$1
  secret=$2
  shift 2
  printf 'user = "%s:%s"\n' "$access" "$secret" | \
    curl --config - --aws-sigv4 'aws:amz:us-east-1:s3' \
    --silent --show-error --max-time 10 --output "$directory/response" \
    --write-out '%{http_code}' "$@"
}

cleanup() {
  rc=0
  for project in a b; do
    # These credentials and object keys were created solely by this test.
    if [ -f "$directory/$project.object" ]; then
      [ "$(s3_request "$root_key" "$root_secret" -X DELETE "$bucket/$fixture/$project/object")" = 204 ] || rc=1
    fi
    if [ -f "$directory/$project.user" ]; then
      key=$(cat "$directory/$project.user")
      rc_step "remove fixture user $project" admin user rm core "$key" || rc=1
    fi
    if [ -f "$directory/$project.json" ]; then
      rc_step "remove fixture policy $project" admin policy rm core "$fixture-$project" || rc=1
    fi
  done
  rm -rf "$directory"
  if [ "$rc" -ne 0 ]; then
    echo "RustFS test fixture cleanup failed for $fixture" >&2
    exit 1
  fi
}
trap cleanup EXIT

provision() {
  project=$1
  key=$2
  secret=$3
  prefix="$fixture/$project"
  jq -n --arg prefix "$prefix" '{
    Version: "2012-10-17",
    Statement: [
      {Effect: "Allow", Action: "s3:ListBucket", Resource: "arn:aws:s3:::ml-datasets",
       Condition: {StringLike: {"s3:prefix": ($prefix + "/*")}}},
      {Effect: "Allow", Action: ["s3:GetObject", "s3:PutObject"],
       Resource: ("arn:aws:s3:::ml-datasets/" + $prefix + "/*")}
    ]
  }' >"$directory/$project.json"
  rc_step "create fixture policy $project" admin policy create core "$fixture-$project" "$directory/$project.json"
  rc_step "create fixture user $project" admin user add core "$key" "$secret"
  printf '%s' "$key" >"$directory/$project.user"
  rc_step "attach fixture policy $project" admin policy attach core "$fixture-$project" --user "$key"
}

expect() {
  expected=$1
  label=$2
  shift 2
  actual=$(s3_request "$@")
  if [ "$actual" != "$expected" ]; then
    echo "$label returned HTTP $actual, expected $expected" >&2
    exit 1
  fi
}

provision a "$key_a" "$secret_a"
provision b "$key_b" "$secret_b"
url_a="$bucket/$fixture/a/object"
url_b="$bucket/$fixture/b/object"
expect 200 'project A put own object' "$key_a" "$secret_a" -X PUT --data-binary a "$url_a"
touch "$directory/a.object"
expect 200 'project B put own object' "$key_b" "$secret_b" -X PUT --data-binary b "$url_b"
touch "$directory/b.object"
expect 200 'project A get own object' "$key_a" "$secret_a" "$url_a"
[ "$(cat "$directory/response")" = a ]
expect 200 'project B get own object' "$key_b" "$secret_b" "$url_b"
[ "$(cat "$directory/response")" = b ]
expect 200 'project A list own prefix' "$key_a" "$secret_a" "$bucket?list-type=2&prefix=$fixture/a/"
grep -Fq "<Key>$fixture/a/object</Key>" "$directory/response"
expect 403 'project A list project B prefix' "$key_a" "$secret_a" "$bucket?list-type=2&prefix=$fixture/b/"
expect 403 'project A list without prefix' "$key_a" "$secret_a" "$bucket?list-type=2"
expect 403 'project A get project B object' "$key_a" "$secret_a" "$url_b"
expect 403 'project A write project B object' "$key_a" "$secret_a" -X PUT --data-binary denied "$url_b"
expect 403 'project B get project A object' "$key_b" "$secret_b" "$url_a"
expect 403 'project B list artifacts' "$key_b" "$secret_b" 'http://rustfs:9000/mlflow-artifacts?list-type=2'
echo 'RustFS scoped identities passed same-project list/get/put and cross-project denial checks'
