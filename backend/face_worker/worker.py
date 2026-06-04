"""
SmartClass Face Recognition Worker
====================================
Standalone script — run in a separate terminal during development:
    python face_worker/worker.py

Environment variables (copy from .env and set in shell, or create face_worker/.env):
    API_BASE_URL          http://localhost:8000
    INTERNAL_API_KEY      worker-shared-secret
    FACE_MATCH_THRESHOLD  0.40
    FACE_VOTE_THRESHOLD   3     (consecutive frames confirming same person before POSTing)
    FACE_COOLDOWN_SECONDS 30    (seconds before re-posting the same student)
    INSIGHTFACE_MODEL     buffalo_sc
    CAMERA_INDEX          0     (cv2.VideoCapture index; 0 = laptop webcam)
    FRAME_SKIP            5     (process every Nth frame, ~6 effective fps at 30fps camera)
    DEVICE_ID             CAM-TEST  (must match a device_id in the cameras table)
"""
import os
import signal
import sys
import time
from pathlib import Path

# Load backend/.env so INTERNAL_API_KEY and other vars are available without manual export
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

import cv2
import numpy as np
import requests
from insightface.app import FaceAnalysis

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
API_BASE_URL          = os.environ.get("API_BASE_URL", "http://localhost:8000")
INTERNAL_API_KEY      = os.environ.get("INTERNAL_API_KEY", "worker-shared-secret")
FACE_MATCH_THRESHOLD  = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.40"))
FACE_VOTE_THRESHOLD   = int(os.environ.get("FACE_VOTE_THRESHOLD", "3"))
FACE_COOLDOWN_SECONDS = int(os.environ.get("FACE_COOLDOWN_SECONDS", "30"))
INSIGHTFACE_MODEL     = os.environ.get("INSIGHTFACE_MODEL", "buffalo_sc")
CAMERA_INDEX          = int(os.environ.get("CAMERA_INDEX", "0"))
FRAME_SKIP            = int(os.environ.get("FRAME_SKIP", "5"))
DEVICE_ID             = os.environ.get("DEVICE_ID", "CAM-TEST")

HEADERS = {"X-Internal-Key": INTERNAL_API_KEY, "Content-Type": "application/json"}

_running = True


def _sigint_handler(sig, frame):
    global _running
    print("\n[worker] Shutting down...")
    _running = False


signal.signal(signal.SIGINT, _sigint_handler)


# ---------------------------------------------------------------------------
# Phase 1 — Initialise InsightFace model (loads buffalo_sc onto CPU)
# ---------------------------------------------------------------------------
def load_face_app() -> FaceAnalysis:
    print(f"[worker] Loading InsightFace model '{INSIGHTFACE_MODEL}' (CPU)...")
    fa = FaceAnalysis(name=INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))
    print("[worker] Model ready.")
    return fa


# ---------------------------------------------------------------------------
# Phase 2 — Poll for active session
# ---------------------------------------------------------------------------
def wait_for_active_session() -> int:
    print(f"[worker] Waiting for an open session on device {DEVICE_ID}...")
    while _running:
        try:
            resp = requests.get(
                f"{API_BASE_URL}/internal/active-session",
                headers=HEADERS,
                params={"device_id": DEVICE_ID},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                session_id = data["session_id"]
                print(f"[worker] Active session found: id={session_id} class_id={data['class_id']}")
                return session_id
            elif resp.status_code != 404:
                print(f"[worker] Unexpected response from active-session: HTTP {resp.status_code} — {resp.text[:120]}")
        except requests.RequestException as exc:
            print(f"[worker] API unreachable: {exc}")
        time.sleep(10)
    return -1


# ---------------------------------------------------------------------------
# Phase 3 — Capture loop with FR-004 multi-frame vote aggregation
# ---------------------------------------------------------------------------
def run_capture_loop(face_app: FaceAnalysis, session_id: int) -> bool:
    """
    Returns True if the session closed naturally (worker should poll for a new one).
    Returns False if _running was set to False (global shutdown).
    """
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[worker] ERROR: Cannot open camera index {CAMERA_INDEX}")
        return False

    print(f"[worker] Camera opened (index={CAMERA_INDEX}). Processing session {session_id}...")

    vote_counts: dict[int, int] = {}    # student_id → consecutive frame hits
    last_posted: dict[int, float] = {}  # student_id → timestamp of last committed match
    frame_count = 0

    while _running:
        ret, frame = cap.read()
        if not ret:
            print("[worker] Camera read error — retrying...")
            time.sleep(0.1)
            continue

        frame_count += 1
        if frame_count % FRAME_SKIP != 0:
            continue

        # Detect faces in this sampled frame
        try:
            faces = face_app.get(frame)
        except Exception as exc:
            print(f"[worker] InsightFace error: {exc}")
            continue

        if faces:
            print(f"[worker] frame {frame_count}: {len(faces)} face(s) detected")
        else:
            print(f"[worker] frame {frame_count}: no face detected")
            continue

        active_student_ids: set[int] = set()

        for face in faces:
            embedding: np.ndarray = face.normed_embedding
            if embedding is None:
                continue

            # --- Dry-run query: get candidate match without writing DB record ---
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/internal/face-match",
                    json={"embedding": embedding.tolist(), "session_id": session_id, "dry_run": True},
                    headers=HEADERS,
                    timeout=2.0,
                )
            except requests.RequestException as exc:
                print(f"[worker] face-match request error: {exc}")
                continue

            if resp.status_code == 404:
                # Session closed while we were in the loop
                print("[worker] Session closed — returning to session discovery.")
                cap.release()
                return True

            if resp.status_code != 200:
                print(f"[worker] face-match error: HTTP {resp.status_code} — {resp.text[:120]}")
                continue

            data = resp.json()
            similarity = data.get("similarity") or 0.0
            if not data.get("matched"):
                reason = data.get("reason", "")
                if reason == "not_enrolled":
                    print(f"[worker] face matched (similarity={similarity:.3f}) but student not enrolled in this class")
                else:
                    print(f"[worker] no match (similarity={similarity:.3f}, threshold={FACE_MATCH_THRESHOLD})")
                    # Flag for admin review — InsightFace already guarantees a real face
                    try:
                        requests.post(
                            f"{API_BASE_URL}/internal/face-review",
                            json={
                                "embedding": embedding.tolist(),
                                "session_id": session_id,
                                "similarity": similarity,
                                "camera_device_id": DEVICE_ID,
                            },
                            headers=HEADERS,
                            timeout=2.0,
                        )
                    except requests.RequestException:
                        pass  # fire-and-forget; don't block capture loop
                continue

            student_id: int = data["student_id"]
            already_present: bool = data.get("already_present", False)

            if already_present:
                print(f"[worker] {data.get('student_name', student_id)} already present — skipping")
                continue

            active_student_ids.add(student_id)
            vote_counts[student_id] = vote_counts.get(student_id, 0) + 1

            print(f"[worker] candidate: {data.get('student_name', student_id)} similarity={similarity:.3f} votes={vote_counts[student_id]}/{FACE_VOTE_THRESHOLD}")

            if vote_counts[student_id] >= FACE_VOTE_THRESHOLD:
                now = time.time()
                cooldown_elapsed = now - last_posted.get(student_id, 0) >= FACE_COOLDOWN_SECONDS

                if cooldown_elapsed:
                    # Commit the match — write attendance record
                    try:
                        commit_resp = requests.post(
                            f"{API_BASE_URL}/internal/face-match",
                            json={"embedding": embedding.tolist(), "session_id": session_id, "dry_run": False},
                            headers=HEADERS,
                            timeout=2.0,
                        )
                    except requests.RequestException as exc:
                        print(f"[worker] commit face-match error: {exc}")
                        continue

                    if commit_resp.status_code == 200:
                        cdata = commit_resp.json()
                        name = cdata.get("student_name", f"id={student_id}")
                        print(f"[worker] MATCH → {name} (similarity={similarity:.3f}, votes={vote_counts[student_id]})")
                        last_posted[student_id] = now
                        vote_counts[student_id] = 0

        # Reset vote count for any student no longer visible this frame
        for sid in list(vote_counts.keys()):
            if sid not in active_student_ids:
                if vote_counts[sid] > 0:
                    vote_counts[sid] = 0

    cap.release()
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    face_app = load_face_app()

    while _running:
        session_id = wait_for_active_session()
        if session_id == -1:
            break

        session_ended_naturally = run_capture_loop(face_app, session_id)
        if not session_ended_naturally:
            break

    print("[worker] Stopped.")


if __name__ == "__main__":
    main()
