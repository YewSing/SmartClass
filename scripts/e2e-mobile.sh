#!/usr/bin/env bash
# Mobile E2E: boot the Android emulator, start backend + Expo, open the app in Expo Go, run a Maestro flow.
# Usage (Git Bash, repo root):  bash scripts/e2e-mobile.sh <student|lecturer> <flow>
#   runs mobile/<app>/e2e/<flow>.yaml, e.g.  bash scripts/e2e-mobile.sh student smoke
# Anything this script starts (uvicorn, Expo, the emulator) is stopped again on exit.
# Env overrides: AVD (default Pixel_4_API_35), E2E_HEADLESS=0 to show the emulator window,
# E2E_API_PORT (default 8000) to run the test backend beside a dev backend.
set -uo pipefail

APP=${1:-}; FLOW=${2:-}
case "$APP" in student|lecturer) ;; *) echo "Usage: $0 <student|lecturer> <flow>"; exit 2;; esac
[ -n "$FLOW" ] || { echo "Usage: $0 <student|lecturer> <flow>"; exit 2; }

root=$(cd "$(dirname "$0")/.." && pwd)
app_dir="$root/mobile/$APP"
flow_file="$app_dir/e2e/$FLOW.yaml"
[ -f "$flow_file" ] || { echo "No flow: $flow_file"; exit 2; }

AVD=${AVD:-Pixel_4_API_35}
API_PORT=${E2E_API_PORT:-8000}   # another port when an everyday dev backend already uses 8000
EXPO_PORT=8081
EXPO_GO=host.exp.exponent
logdir="$root/.claude/logs"; mkdir -p "$logdir"
stamp=$(date +%Y%m%d-%H%M%S)

# --- tools on PATH -----------------------------------------------------------
to_unix() { if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else echo "$1"; fi; }
to_win()  { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi; }
SDK=$(to_unix "${ANDROID_HOME:-${LOCALAPPDATA:-$HOME/AppData/Local}/Android/Sdk}")
export ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
export PATH="$SDK/platform-tools:$SDK/emulator:$PATH"
command -v adb >/dev/null || { echo "adb not found under $SDK/platform-tools"; exit 1; }
command -v emulator >/dev/null || { echo "emulator not found under $SDK/emulator"; exit 1; }

# Maestro: an existing ~/.maestro install, else one in the repo's git-ignored .tools/ (installed on demand)
tools_maestro="$root/.tools/maestro"
maestro_home() {
  local d
  for d in "$HOME/.maestro" "$tools_maestro"; do
    [ -d "$d/lib" ] && { echo "$d"; return; }
  done
}
run_maestro() {
  local home; home=$(maestro_home)
  if command -v cygpath >/dev/null 2>&1; then
    # Windows: start the CLI's main class directly. Both bundled launchers break here: the .bat's
    # `for /f ... cmd /c` line fails on paths with spaces ("UM Documents"), and the sh one builds a
    # ':'-separated classpath that Windows Java can't read.
    local java=java
    [ -n "${JAVA_HOME:-}" ] && java="$(to_unix "$JAVA_HOME")/bin/java"
    "$java" --enable-native-access=ALL-UNNAMED -classpath "$(to_win "$home/lib")\\*" maestro.cli.AppKt "$@"
  else
    "$home/bin/maestro" "$@"
  fi
}
export MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true
if [ -z "$(maestro_home)" ]; then
  echo "== installing Maestro CLI into .tools/maestro"
  mkdir -p "$root/.tools"
  tmp_zip="$root/.tools/maestro.zip"
  curl -fsSL -o "$tmp_zip" https://github.com/mobile-dev-inc/maestro/releases/latest/download/maestro.zip \
    || { echo "Maestro download failed"; exit 1; }
  # the zip holds a single top-level maestro/ folder (bin/, lib/)
  if command -v unzip >/dev/null 2>&1; then
    unzip -q -o "$tmp_zip" -d "$root/.tools"
  else
    powershell.exe -NoProfile -Command "Expand-Archive -Force '$(to_win "$tmp_zip")' '$(to_win "$root/.tools")'"
  fi
  rm -f "$tmp_zip"
  [ -n "$(maestro_home)" ] || { echo "Maestro install failed (expected $tools_maestro/lib)"; exit 1; }
fi

# --- cleanup -----------------------------------------------------------------
started_pids=()          # bash PIDs of processes we started (uvicorn, Expo)
# A flow may bring test data: e2e/<flow>.setup.sh is run with `setup` before Maestro and `teardown` on exit.
flow_setup="$app_dir/e2e/$FLOW.setup.sh"
flow_setup_ran=""
booted_emulator=""       # serial of the emulator if we booted it
kill_tree() {            # Windows needs taskkill /T to stop node/python child processes
  local pid=$1 winpid
  winpid=$(cat "/proc/$pid/winpid" 2>/dev/null || true)
  if [ -n "$winpid" ] && command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$winpid" >/dev/null 2>&1 || true
  fi
  kill "$pid" 2>/dev/null || true
}
cleanup() {
  local code=$?
  trap - EXIT INT TERM
  echo "== cleanup"
  [ -n "$flow_setup_ran" ] && { bash "$flow_setup" teardown || echo "   (flow teardown failed)"; }
  for pid in "${started_pids[@]}"; do kill_tree "$pid"; done
  if [ -n "$booted_emulator" ]; then
    adb -s "$booted_emulator" emu kill >/dev/null 2>&1 || true
    [ -n "${emu_pid:-}" ] && kill_tree "$emu_pid"
  fi
  [ -n "${lock_held:-}" ] && rm -rf "$lock_dir"
  exit "$code"
}
trap cleanup EXIT INT TERM

# One Maestro run at a time across all worktrees of this repo: there is one emulator, and Expo
# (:8081) and the API port are shared. The lock lives in the shared .git dir, so a loop in another
# worktree waits here instead of fighting over the emulator. A lock whose owner is gone, or older
# than 40 minutes, is stale and taken over.
lock_dir="$(cd "$root" && cd "$(git rev-parse --git-common-dir)" && pwd)/e2e-mobile.lock"
lock_wait_until=$(( $(date +%s) + 45*60 ))
until mkdir "$lock_dir" 2>/dev/null; do
  owner=$(cat "$lock_dir/pid" 2>/dev/null || true)
  age=$(( $(date +%s) - $(cat "$lock_dir/since" 2>/dev/null || date +%s) ))
  if { [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; } || [ "$age" -gt $((40*60)) ]; then
    echo "== removing a stale E2E lock (pid ${owner:-?}, ${age}s old)"; rm -rf "$lock_dir"; continue
  fi
  [ "$(date +%s)" -lt "$lock_wait_until" ] || { echo "Gave up waiting for the E2E lock held by pid $owner"; exit 1; }
  echo "== another worktree is running a Maestro flow (pid $owner); waiting"; sleep 20
done
lock_held=1; echo $$ > "$lock_dir/pid"; date +%s > "$lock_dir/since"

port_busy() { curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$1/" ; }
wait_for() {             # wait_for <seconds> <description> <command...>
  local secs=$1 what=$2; shift 2
  for _ in $(seq 1 "$secs"); do "$@" >/dev/null 2>&1 && return 0; sleep 1; done
  echo "Timed out after ${secs}s waiting for $what"; return 1
}

# E2E must never call the real LLM. A backend we didn't start may not have LLM_FAKE=1, so ours runs
# beside an everyday dev backend on :8000 instead of using it.
if [ -z "${E2E_API_PORT:-}" ] && curl -s --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null; then
  echo "== a dev backend is using :$API_PORT; the E2E backend runs on :8003"
  API_PORT=8003
fi
if curl -s --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null; then
  echo "A backend is already running on :$API_PORT. E2E needs its own with LLM_FAKE=1. Stop it and retry."; exit 1
fi

# --- emulator ----------------------------------------------------------------
serial=$(adb devices | awk '/^emulator-[0-9]+\tdevice/ {print $1; exit}')
if [ -z "$serial" ]; then
  emulator -list-avds | tr -d '\r' | grep -qx "$AVD" || { echo "AVD $AVD not found (emulator -list-avds)"; exit 1; }
  echo "== booting emulator $AVD"
  emu_flags=(-avd "$AVD" -no-audio -no-boot-anim -no-snapshot-save)
  [ "${E2E_HEADLESS:-1}" = "1" ] && emu_flags+=(-no-window)
  emulator "${emu_flags[@]}" > "$logdir/emulator-$stamp.log" 2>&1 &
  emu_pid=$!
  wait_for 120 "emulator to appear in adb" sh -c "adb devices | grep -q '^emulator-[0-9]*\sdevice'" || exit 1
  serial=$(adb devices | awk '/^emulator-[0-9]+\tdevice/ {print $1; exit}')
  booted_emulator=$serial
  wait_for 300 "Android boot" sh -c "adb -s $serial shell getprop sys.boot_completed | grep -q 1" || exit 1
else
  echo "== using running emulator $serial"
fi
export ANDROID_SERIAL=$serial
adb shell input keyevent 82 >/dev/null 2>&1 || true     # unlock screen

# --- backend -----------------------------------------------------------------
# E2E never calls the real LLM: the backend we start gives canned replies (LLM_FAKE=1). Only a by-hand
# look at real answers turns this off with E2E_LLM_FAKE=0 (see mobile/student/e2e/assistant-look.yaml).
echo "== starting backend on :$API_PORT (LLM_FAKE=${E2E_LLM_FAKE:-1})"
(cd "$root/backend" && docker compose up -d >/dev/null 2>&1) || echo "   (docker compose up failed; continuing)"
# The schedule job and the Moodle Attendance sync are off: flows start classes themselves, and test
# sessions must never be written into Moodle. YouTube is off too (no key), so "Find related videos"
# shows search keywords instead of calling the real API.
(cd "$root/backend" && LLM_FAKE="${E2E_LLM_FAKE:-1}" YOUTUBE_API_KEY="" SESSION_SCHEDULER_INTERVAL_SECONDS=0 \
  MOODLE_ATTENDANCE_SYNC_INTERVAL_SECONDS=0 MOODLE_ATTENDANCE_CHECK_INTERVAL_SECONDS=0 exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT") \
  > "$logdir/e2e-backend-$stamp.log" 2>&1 &
started_pids+=($!)
wait_for 60 "backend /health" curl -sf "http://127.0.0.1:$API_PORT/health" || { tail -20 "$logdir/e2e-backend-$stamp.log"; exit 1; }

# --- Expo --------------------------------------------------------------------
if port_busy "$EXPO_PORT"; then
  echo "== :$EXPO_PORT is in use (an everyday Expo dev server?); E2E Expo runs on :8083"
  EXPO_PORT=8083
fi
if port_busy "$EXPO_PORT"; then
  echo "Port $EXPO_PORT is already in use (another Expo dev server?). Stop it and retry."; exit 1
fi
[ -d "$app_dir/node_modules" ] || (cd "$app_dir" && npm install --legacy-peer-deps --no-audit --no-fund) || exit 1

expo_args=(start --port "$EXPO_PORT")
if ! adb shell pm list packages "$EXPO_GO" | grep -q "$EXPO_GO"; then
  echo "== Expo Go not installed; expo start --android will install it"
  expo_args+=(--android)
fi
echo "== starting Expo for $APP on :$EXPO_PORT"
(cd "$app_dir" && CI=1 EXPO_PUBLIC_API_URL="http://10.0.2.2:$API_PORT" exec npx expo "${expo_args[@]}") \
  > "$logdir/e2e-expo-$APP-$stamp.log" 2>&1 &
started_pids+=($!)
wait_for 120 "Expo dev server" curl -sf "http://127.0.0.1:$EXPO_PORT/status" || { tail -20 "$logdir/e2e-expo-$APP-$stamp.log"; exit 1; }
wait_for 300 "Expo Go install" sh -c "adb shell pm list packages $EXPO_GO | grep -q $EXPO_GO" || { tail -20 "$logdir/e2e-expo-$APP-$stamp.log"; exit 1; }

# --- open the app in Expo Go and run the flow --------------------------------
echo "== opening $APP in Expo Go"
adb reverse "tcp:$EXPO_PORT" "tcp:$EXPO_PORT" >/dev/null 2>&1 || true
adb shell am force-stop "$EXPO_GO" >/dev/null 2>&1 || true
adb shell am start -a android.intent.action.VIEW -d "exp://127.0.0.1:$EXPO_PORT" "$EXPO_GO" >/dev/null

if [ -f "$flow_setup" ]; then
  # flow setup scripts that call the API in the background read this
  export E2E_API_URL="http://127.0.0.1:$API_PORT"
  echo "== flow setup $(basename "$flow_setup")"
  flow_setup_ran=1
  bash "$flow_setup" setup || { echo "Flow setup failed"; exit 1; }
fi

echo "== maestro test $flow_file"
run_maestro test "$(to_win "$flow_file")" --debug-output "$(to_win "$logdir/maestro-$APP-$FLOW-$stamp")"
status=$?
[ $status -eq 0 ] && echo "PASS: $APP/$FLOW" || echo "FAIL: $APP/$FLOW (logs in $logdir)"
exit $status
