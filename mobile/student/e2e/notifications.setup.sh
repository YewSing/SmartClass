#!/usr/bin/env bash
# Test data for notifications.yaml (plan-shino.md S19), run by scripts/e2e-mobile.sh:
#   setup     seeds three unread notifications for student4 (urgent, important with a link, general)
#             and starts the actor that sends a test notification once they are all read
#   teardown  removes them and restores student4's own notifications and preferences
# setup runs before the flow logs in, so student4 must already exist in SmartClass.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
USER_EMAIL=student4@example.com
case "${1:-}" in
  setup)
    python scripts/e2e_notifications.py seed --user "$USER_EMAIL"
    actor_log="$(python -c 'import tempfile;print(tempfile.gettempdir())')/smartclass-e2e-notifications-actor.log"
    nohup python scripts/e2e_notifications.py actor --user "$USER_EMAIL" --api "${E2E_API_URL:-http://127.0.0.1:8000}" \
      > "$actor_log" 2>&1 &
    echo "actor running in the background; log: $actor_log"
    ;;
  teardown) python scripts/e2e_notifications.py clean --user "$USER_EMAIL" ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
