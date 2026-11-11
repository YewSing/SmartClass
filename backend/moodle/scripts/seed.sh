#!/usr/bin/env bash
# Seed courses/users/enrolments/materials. Usage: seed.sh [--dry-run]
# A git-ignored backend/moodle/seed_config.local.json (same "users"/"enrolments" shape) adds
# personal test accounts, e.g. one with your real matric number, without committing them.
export MSYS_NO_PATHCONV=1
container="${MOODLE_CONTAINER:-smartclass-moodle-moodle-1}"
local_conf="$(dirname "$0")/../seed_config.local.json"
if [ -f "$local_conf" ]; then
  docker cp "$local_conf" "$container:/tmp/seed_config.local.json"
  docker exec -u 0 "$container" chmod 644 /tmp/seed_config.local.json
else
  docker exec -u 0 "$container" rm -f /tmp/seed_config.local.json
fi
exec docker exec -u daemon "$container" php /scripts/seed_courses.php "$@"
