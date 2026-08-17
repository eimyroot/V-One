#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 2 || "$#" -gt 3 ]]; then
  echo "usage: smoke_product_image.sh IMAGE RUN_NAMESPACE [EVIDENCE_DIRECTORY]" >&2
  exit 2
fi

image="$1"
run_namespace="$2"
evidence_directory="${3:-}"
if [[ ! "$image" =~ ^[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] ||
  [[ ! "$run_namespace" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$ ]]; then
  echo "image and run namespace must use safe identifier characters" >&2
  exit 2
fi
if [[ -n "$evidence_directory" ]]; then
  if [[ "$evidence_directory" != /* || ! -d "$evidence_directory" ||
    -L "$evidence_directory" ]]; then
    echo "evidence directory must be an existing absolute real directory" >&2
    exit 2
  fi
  physical_evidence_directory="$(cd "$evidence_directory" && pwd -P)"
  if [[ "$physical_evidence_directory" != "$evidence_directory" ]]; then
    echo "evidence directory must not traverse symlinked components" >&2
    exit 2
  fi
  umask 077
  set -o noclobber
fi

container="voodoo-one-${run_namespace}"
data_volume="voodoo-one-data-${run_namespace}"
container_created=0
volume_created=0
cleanup() {
  status="$?"
  trap - EXIT
  cleanup_failed=0
  if [[ "$container_created" -eq 1 ]]; then
    docker rm --force "$container" >/dev/null 2>&1 || cleanup_failed=1
  fi
  if [[ "$volume_created" -eq 1 ]]; then
    docker volume rm --force "$data_volume" >/dev/null 2>&1 || cleanup_failed=1
  fi
  if [[ "$cleanup_failed" -ne 0 && -n "$evidence_directory" ]]; then
    echo "VOODOO_SMOKE_ERROR=capture_cleanup_failed" >&2
    exit 97
  fi
  exit "$status"
}
trap cleanup EXIT

if docker container inspect "$container" >/dev/null 2>&1 ||
  docker volume inspect "$data_volume" >/dev/null 2>&1; then
  if [[ -n "$evidence_directory" ]]; then
    echo "VOODOO_SMOKE_ERROR=task_resource_exists" >&2
  fi
  exit 2
fi

docker volume create \
  --label "voodoo.capture.namespace=$run_namespace" \
  "$data_volume" >/dev/null
volume_created=1
test "$(docker volume inspect \
  --format '{{index .Labels "voodoo.capture.namespace"}}' \
  "$data_volume")" = "$run_namespace"
docker create \
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
container_created=1
docker start "$container" >/dev/null

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
health_payload="$(curl --fail --silent --show-error \
  http://127.0.0.1:18000/api/v1/health)"
if [[ -n "$evidence_directory" ]]; then
  printf '%s\n' "$health_payload" >"$evidence_directory/08_APPLICATION_HEALTH.json"
fi
printf '%s\n' "$health_payload" | \
  docker exec --interactive "$container" python -c 'import json,sys; data=json.load(sys.stdin); assert data["status"] == "HEALTHY"; assert data["database_backend"] == "sqlite"; assert data["schema_version"] == 10; assert data["production_effects"] == "DISABLED"'

if [[ -n "$evidence_directory" ]]; then
  docker_health_status=""
  for attempt in {1..45}; do
    docker_health_status="$(docker inspect \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
      "$container")"
    if [[ "$docker_health_status" == "healthy" ]]; then
      break
    fi
    if [[ "$docker_health_status" == "unhealthy" || "$attempt" == "45" ]]; then
      echo "VOODOO_SMOKE_ERROR=docker_health_unverified" >&2
      exit 3
    fi
    sleep 1
  done
  docker inspect --format '{{json .State.Health}}' "$container" \
    >"$evidence_directory/07_CONTAINER_HEALTH.json"
  docker inspect --format '{{.Image}}' "$container" \
    >"$evidence_directory/07_CONTAINER_IMAGE_ID.txt"
  docker logs --tail 200 "$container" \
    >"$evidence_directory/05_RUNTIME_LOG.txt" 2>&1
fi
