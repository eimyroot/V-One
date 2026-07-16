#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "usage: smoke_product_image.sh IMAGE RUN_NAMESPACE" >&2
  exit 2
fi

image="$1"
run_namespace="$2"
if [[ ! "$image" =~ ^[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] ||
  [[ ! "$run_namespace" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$ ]]; then
  echo "image and run namespace must use safe identifier characters" >&2
  exit 2
fi

container="voodoo-one-${run_namespace}"
data_volume="voodoo-one-data-${run_namespace}"
cleanup() {
  docker rm --force "$container" >/dev/null 2>&1 || true
  docker volume rm --force "$data_volume" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker volume create "$data_volume" >/dev/null
docker run --detach \
  --name "$container" \
  --read-only \
  --tmpfs /tmp:size=64m,mode=1777 \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  --pids-limit 128 \
  --mount "type=volume,source=$data_volume,target=/app/storage/product" \
  --publish 127.0.0.1:18000:8000 \
  --env VOODOO_ENV=local \
  --env VOODOO_ROOT=/app \
  --env VOODOO_DATABASE_BACKEND=sqlite \
  --env VOODOO_PRODUCT_DB=/app/storage/product/voodoo_one.sqlite3 \
  --env VOODOO_PRODUCT_SANDBOX_ROOT=/app/storage/product/sandboxes \
  --env VOODOO_SESSION_SIGNING_SECRET=ci-session-signing-secret-00000000000000000000000000000000 \
  --env VOODOO_BOOTSTRAP_TOKEN=ci-bootstrap-token-000000000000000000000000 \
  --env VOODOO_TRUSTED_HOSTS=127.0.0.1 \
  --env VOODOO_ALLOW_PRODUCTION_EFFECTS=false \
  "$image" >/dev/null

for attempt in {1..30}; do
  if curl --fail --silent --show-error \
    http://127.0.0.1:18000/api/v1/health >/dev/null; then
    break
  fi
  if [[ "$attempt" == "30" ]]; then
    docker logs "$container"
    exit 1
  fi
  sleep 1
done

health_headers="$(curl --fail --silent --show-error --dump-header - \
  --output /dev/null http://127.0.0.1:18000/api/v1/health)"
grep --ignore-case --quiet --fixed-strings "cache-control: no-store" <<<"$health_headers"
grep --ignore-case --quiet --fixed-strings "content-security-policy:" <<<"$health_headers"
if grep --ignore-case --quiet "^server:" <<<"$health_headers"; then
  exit 1
fi

test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --header 'Host: evil.example' http://127.0.0.1:18000/api/v1/health)" = "400"
curl --fail --silent --show-error http://127.0.0.1:18000/api/v1/health | \
  python -c 'import json,sys; data=json.load(sys.stdin); assert data["status"] == "HEALTHY"; assert data["database_backend"] == "sqlite"; assert data["schema_version"] == 6; assert data["production_effects"] == "DISABLED"'
