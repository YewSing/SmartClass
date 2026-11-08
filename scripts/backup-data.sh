#!/usr/bin/env bash
# Snapshot the Docker data volumes (app DB + simulated Moodle) to ~/smartclass-backups/<timestamp>/.
# Stops the two stacks for a few seconds so the database files are consistent, then starts them again.
# Keeps the newest 3 snapshots. Restore with: bash scripts/restore-data.sh [timestamp]
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
VOLUMES="backend_pgdata smartclass-moodle_moodle_db_data smartclass-moodle_moodle_data smartclass-moodle_moodle_moodledata"
ts=$(date +%Y%m%d-%H%M%S)
dest="$HOME/smartclass-backups/$ts"; mkdir -p "$dest"
hostdest=$(cygpath -w "$dest" 2>/dev/null || echo "$dest")

(cd "$root/backend" && docker compose stop -t 20) > /dev/null
(cd "$root/backend/moodle" && docker compose stop -t 20) > /dev/null
for v in $VOLUMES; do
  MSYS_NO_PATHCONV=1 docker run --rm -v "$v:/v:ro" -v "$hostdest:/b" alpine tar czf "/b/$v.tgz" -C /v .
done
(cd "$root/backend" && docker compose up -d) > /dev/null
(cd "$root/backend/moodle" && docker compose up -d) > /dev/null

ls -1d "$HOME"/smartclass-backups/*/ | sort | head -n -3 | xargs -r rm -rf
echo "backup: $dest ($(du -sh "$dest" | cut -f1))"
