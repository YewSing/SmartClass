#!/usr/bin/env bash
# Restore the Docker data volumes from a backup made by backup-data.sh.
# Usage: bash scripts/restore-data.sh            -> newest backup
#        bash scripts/restore-data.sh 20261109-0100
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
VOLUMES="backend_pgdata smartclass-moodle_moodle_db_data smartclass-moodle_moodle_data smartclass-moodle_moodle_moodledata"
src="$HOME/smartclass-backups/${1:-$(ls -1 "$HOME/smartclass-backups" | sort | tail -1)}"
[ -d "$src" ] || { echo "no backup at $src"; exit 1; }
hostsrc=$(cygpath -w "$src" 2>/dev/null || echo "$src")
read -r -p "Replace current app DB and Moodle data with $src ? [y/N] " ok; [ "$ok" = "y" ] || exit 1

(cd "$root/backend" && docker compose stop -t 20) > /dev/null
(cd "$root/backend/moodle" && docker compose stop -t 20) > /dev/null
for v in $VOLUMES; do
  MSYS_NO_PATHCONV=1 docker run --rm -v "$v:/v" -v "$hostsrc:/b:ro" alpine sh -c "rm -rf /v/* /v/..?* /v/.[!.]* 2>/dev/null; tar xzf /b/$v.tgz -C /v"
done
(cd "$root/backend" && docker compose up -d) > /dev/null
(cd "$root/backend/moodle" && docker compose up -d) > /dev/null
echo "restored from $src"
