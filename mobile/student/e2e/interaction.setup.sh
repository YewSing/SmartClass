#!/usr/bin/env bash
# Test data for interaction.yaml, run by scripts/e2e-mobile.sh:
#   setup     opens an interaction session with a live poll on student4's enrolled class
#   teardown  removes the seeded session, poll, votes, reactions and IDU signals
# setup runs before the flow logs in, so student4 must already exist in SmartClass
# and be enrolled in at least one course.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)    python scripts/e2e_student_interaction.py setup --student student4@example.com ;;
  teardown) python scripts/e2e_student_interaction.py teardown ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
