#!/usr/bin/env bash
# Configure Moodle and write the service token to backend/moodle/.env.moodle (Git Bash).
# Installs the mod_attendance plugin (first run needs internet inside the container), runs Moodle's
# upgrade so it is registered, then sets up the web services and the "smartclass" service token.
set -euo pipefail
export MSYS_NO_PATHCONV=1
C=${MOODLE_CONTAINER:-smartclass-moodle-moodle-1}
HERE="$(cd "$(dirname "$0")/.." && pwd)"
docker exec -u daemon "$C" php /scripts/install_attendance.php
docker exec -u daemon "$C" php /bitnami/moodle/admin/cli/upgrade.php --non-interactive
OUT=$(docker exec -u daemon "$C" php /scripts/configure_moodle.php)
echo "$OUT"
TOKEN=$(echo "$OUT" | grep '^SMARTCLASS_SVC_TOKEN=' | cut -d= -f2)
printf 'MOODLE_URL=http://localhost:8080\nMOODLE_TOKEN=%s\n' "$TOKEN" > "$HERE/.env.moodle"
echo "Wrote $HERE/.env.moodle"
