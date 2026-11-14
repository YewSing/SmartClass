#!/usr/bin/env bash
# Test data for interaction.yaml, run by scripts/e2e-mobile.sh:
#   setup     opens an interaction session with a live poll on lecturer1's WIF3001 lecture
#   teardown  removes the seeded session, poll, votes, reactions and IDU signals
# setup runs before the flow logs in, so lecturer1 must already exist in SmartClass
# and teach WIF3001.
set -euo pipefail
cd "$(dirname "$0")/../../../backend"
case "${1:-}" in
  setup)    python scripts/e2e_lecturer_interaction.py setup --lecturer lecturer1@example.com --course WIF3001 ;;
  teardown) python scripts/e2e_lecturer_interaction.py teardown ;;
  *) echo "Usage: $0 setup|teardown"; exit 2 ;;
esac
