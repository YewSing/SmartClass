#!/usr/bin/env bash
# PostToolUse hook: after a .py file is written/edited, report ruff errors in that file back to Claude.
f=$(python -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
case "$f" in
  *.py)
    if ! out=$(ruff check --quiet "$f" 2>&1); then
      { echo "ruff found problems in $f:"; echo "$out" | head -30; } >&2
      exit 2
    fi ;;
esac
exit 0
