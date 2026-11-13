#!/usr/bin/env bash
# Test data for assistant.yaml, run by scripts/e2e-mobile.sh:
#   setup     one indexed material + question trends for WIF3001 (lecturer1's course)
#   teardown  removes that material and the seeded students' chats again
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)    python scripts/e2e_assistant.py seed     --course WIF3001 ;;
  teardown) python scripts/e2e_assistant.py teardown --course WIF3001 ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
