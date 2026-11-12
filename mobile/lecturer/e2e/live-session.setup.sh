#!/usr/bin/env bash
# Test data for live-session.yaml, run by scripts/e2e-mobile.sh:
#   setup     checks lecturer1's WIF3001 lecture has no session open
#   teardown  deletes the session the flow started (and its records)
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)    python scripts/e2e_live_session.py setup    --course WIF3001 ;;
  teardown) python scripts/e2e_live_session.py teardown --course WIF3001 ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
