#!/usr/bin/env bash
# Test data for flag-alert.yaml, run by scripts/e2e-mobile.sh:
#   setup     seeds E2E045 (the flag) and E2E046 for student4, then starts the actor that flags
#             E2E045 as the student once the lecturer taps "+15 min"
#   teardown  stops the actor and removes the courses, camera and synthetic face vector
# setup runs before the flow logs in, so student4 and lecturer1 must already exist in SmartClass.
# If it exits with "No SmartClass student/lecturer", sign them in once.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)
    python scripts/e2e_flags.py seed --student student4@example.com --lecturer lecturer1@example.com
    actor_log="$(python -c 'import tempfile;print(tempfile.gettempdir())')/smartclass-e2e-flags-actor.log"
    nohup python scripts/e2e_flags.py actor --mode lecturer --api "${E2E_API_URL:-http://127.0.0.1:8000}" \
      > "$actor_log" 2>&1 &
    echo "actor running in the background; log: $actor_log"
    ;;
  teardown) python scripts/e2e_flags.py clean ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
