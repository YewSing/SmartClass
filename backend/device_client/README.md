# SmartClass camera device client

Runs on the Raspberry Pi at the classroom door, or on a laptop with a USB webcam used as the
room's backup camera (FR-409 — same code, the room's own device key). It:

- sends `POST /device/heartbeat` every 20 s, also while idle;
- polls `GET /device/session` and opens the camera **only** while a session is open for its room
  (FR-401), releasing it when the session closes;
- detects faces locally with OpenCV's bundled Haar cascade (no model download, fine on a Pi);
- crops each face with a 30 % margin (longest side ≤ 320 px, JPEG q90) and posts the crops of one
  frame to `POST /device/faces`; the server embeds, matches and votes (FR-402–FR-405).

Faces and crops are never written to disk (NFR-01), and the key is never printed or logged.

## Get a key

Each device has its own key, shown once. An admin registers the device on the Devices page (or
calls `POST /admin/devices/{id}/regenerate-key`). For the seeded test room's camera:

```bash
cd backend
python scripts/device_key.py CAM-TEST     # prints the new key; copy it
```

The old key stops working as soon as a new one is issued.

## Run on a laptop webcam

```bash
cd backend
DEVICE_KEY=scd_... python -m device_client --camera 0
```

The backup webcam uses the room's key, so to the server it is the same device (FR-409).

## Run on the Pi

Copy the `device_client` folder (no backend code needed), install the requirements (or
`sudo apt install python3-opencv` instead of `opencv-python`), then:

```bash
DEVICE_KEY=scd_... SMARTCLASS_API_URL=http://<server>:8000 python -m device_client --camera 0
```

## Flags and environment

| Flag | Env | Default | Meaning |
| --- | --- | --- | --- |
| `--api` | `SMARTCLASS_API_URL` (then `API_BASE_URL`) | `http://localhost:8000` | server base URL |
| `--key` | `DEVICE_KEY` | — | this device's key (required) |
| `--camera` | `CAMERA_INDEX` | `0` | `cv2.VideoCapture` index; 0 = laptop webcam |
| `--fps` | — | `4` | frames analysed per second |
| `--poll-seconds` | — | `5` | seconds between checks for an open session |
| `--heartbeat-seconds` | — | `20` | seconds between heartbeats |
| `--min-face` | — | `60` | smallest face (pixels) the detector reports |

Flags override the environment. No `.env` file is read.

## Not built yet

FR-411 offline buffering: while the server is unreachable frames are dropped (the client logs,
waits 1 s and carries on). Replaying them later needs a `captured_at` on `POST /device/faces` so the
server can still compute Present/Late correctly.
