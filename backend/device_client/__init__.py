"""SmartClass camera device client (FR-401, FR-402, FR-409).

Runs on a Raspberry Pi with a camera, or on a laptop with a USB webcam used as the room's backup
camera (FR-409). It heartbeats, polls `GET /device/session`, opens the camera only while a session
is open, detects faces locally with OpenCV's Haar cascade, and posts the JPEG crops of one frame
to `POST /device/faces`; the server does embedding, matching and voting.

Copy this folder to the Pi: it does not need the backend code (`app/`). Run it from the folder's
parent with `python -m device_client --camera 0`, with the room's device key in `DEVICE_KEY`.
Nothing is written to disk (NFR-01).
"""
