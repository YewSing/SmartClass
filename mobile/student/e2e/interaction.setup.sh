#!/usr/bin/env bash
set -euo pipefail
app_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$app_dir/../../../backend"
export PYTHONPATH=.
case "${1:-}" in
  setup)
    python "$app_dir/interaction_fixture.py" seed
    nohup python "$app_dir/interaction_fixture.py" close-after-signal >/dev/null 2>&1 </dev/null &
    ;;
  teardown) python "$app_dir/interaction_fixture.py" clean ;;
  *) exit 2 ;;
esac
