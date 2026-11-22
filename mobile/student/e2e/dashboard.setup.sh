#!/usr/bin/env bash
# Test data for dashboard.yaml (plan-shino.md S20), run by scripts/e2e-mobile.sh:
#   setup     seeds three unread notifications for student4 (urgent, important with a link, general)
#   teardown  removes them and restores student4's own notifications and preferences
# The Moodle part of the dashboard comes from student4's real sign-in (S16 snapshot), so it isn't seeded.
# setup runs before the flow logs in, so student4 must already exist in SmartClass.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
USER_EMAIL=student4@example.com
case "${1:-}" in
  setup)    python scripts/e2e_notifications.py seed --user "$USER_EMAIL" ;;
  teardown) python scripts/e2e_notifications.py clean --user "$USER_EMAIL" ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
