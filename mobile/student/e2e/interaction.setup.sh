#!/usr/bin/env bash
# Test data for interaction.yaml (plan-shino.md S38), run by scripts/e2e-mobile.sh:
#   setup     makes course E2E038 for student4 plus one classmate, starts its class now, and starts
#             the actor (classmate asks, lecturer opens a quick question, answers student4's question,
#             starts a poll, then ends the class after an "I don't understand" press)
#   teardown  removes the course and everything made with it
# setup runs before the flow logs in, so student4 must already exist in SmartClass.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
USER_EMAIL=student4@example.com
case "${1:-}" in
  setup)
    python scripts/e2e_student_interaction.py setup --student "$USER_EMAIL"
    actor_log="$(python -c 'import tempfile;print(tempfile.gettempdir())')/smartclass-e2e-student-interaction-actor.log"
    nohup python scripts/e2e_student_interaction.py actor --api "${E2E_API_URL:-http://127.0.0.1:8000}" \
      > "$actor_log" 2>&1 &
    echo "actor running in the background; log: $actor_log"
    ;;
  teardown) python scripts/e2e_student_interaction.py teardown ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
