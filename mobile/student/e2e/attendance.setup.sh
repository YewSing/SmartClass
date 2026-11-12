#!/usr/bin/env bash
# Test data for attendance.yaml, run by scripts/e2e-mobile.sh:
#   setup     seeds course E2E039 for student4 (four closed sessions: present, late, excused, absent)
#   teardown  removes the course and everything seeded with it
# setup runs before the flow logs in, so student4 must already exist in SmartClass (any earlier
# student4 login or a Moodle sync). If it exits with "No SmartClass student", sign student4 in once.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)    python scripts/e2e_student_attendance.py seed  --student student4@example.com ;;
  teardown) python scripts/e2e_student_attendance.py clean ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
