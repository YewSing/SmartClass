#!/usr/bin/env bash
# Test data for face-verification.yaml, run by scripts/e2e-mobile.sh:
#   setup     one pending face enrolment by student8 (in lecturer1's WIF3001 and WIF3004)
#   teardown  removes student8's face data again, approved or not
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)    python scripts/e2e_face_review.py seed  --student student8@example.com ;;
  teardown) python scripts/e2e_face_review.py clean --student student8@example.com ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
