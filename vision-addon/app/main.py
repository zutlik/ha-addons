import asyncio
import os
import time
import logging
import threading
import numpy as np

# Must be set before cv2 is imported so ffmpeg uses TCP for RTSP (reduces decode errors and packet loss)
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
import cv2
from collections import deque

from face_engine import FaceEngine
from gesture_engine import GestureEngine
from ha_client import fire_event, update_sensors
from web_ui import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STREAM_URL = os.environ.get("STREAM_URL", "/dev/video0")
DETECTION_FPS = int(os.environ.get("DETECTION_FPS", "5"))
FACE_CONFIDENCE = float(os.environ.get("FACE_CONFIDENCE", "0.6"))
GESTURE_CONFIDENCE = float(os.environ.get("GESTURE_CONFIDENCE", "0.7"))
GESTURE_COOLDOWN = int(os.environ.get("GESTURE_COOLDOWN", "2"))
MOTION_COOLDOWN = int(os.environ.get("MOTION_COOLDOWN", "5"))
GESTURE_HOLD_SECONDS = 1.5  # gesture must be held this long to fire


class VisionLoop:
    def __init__(self):
        self.face_engine = FaceEngine(FACE_CONFIDENCE)
        self.gesture_engine = GestureEngine(GESTURE_CONFIDENCE)
        self.running = False

        # Shared state for web UI
        self.latest_frame: bytes = b""
        self.latest_faces: list = []
        self.latest_gesture: str | None = None
        self.known_persons: dict = {}  # name -> currently detected bool
        self.frame_lock = threading.Lock()

        # Gesture hold tracking
        self._gesture_candidate: str | None = None
        self._gesture_start: float = 0.0
        self._gesture_fired_at: float = 0.0  # last time we fired this gesture

        # Motion tracking
        self._prev_gray = None
        self._motion_fired_at: float = 0.0

        # Face cooldown per person
        self._person_fired_at: dict = {}

    def _detect_motion(self, gray: np.ndarray) -> bool:
        if self._prev_gray is None:
            self._prev_gray = gray
            return False
        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray
        return float(np.mean(diff)) > 5.0

    async def _handle_gesture(self, gesture: str | None):
        now = time.time()
        if gesture is None:
            self._gesture_candidate = None
            self._gesture_start = 0.0
            return

        if gesture != self._gesture_candidate:
            self._gesture_candidate = gesture
            self._gesture_start = now
            return

        held_for = now - self._gesture_start
        if held_for < GESTURE_HOLD_SECONDS:
            return

        # Gesture held long enough — check cooldown
        last_fired = self._gesture_fired_at
        if now - last_fired < GESTURE_COOLDOWN:
            return

        self._gesture_fired_at = now
        self._gesture_candidate = None
        self._gesture_start = 0.0

        logger.info(f"Gesture fired: {gesture}")
        await fire_event("vision_addon.gesture_detected", {"gesture": gesture})

    async def _handle_faces(self, face_result: dict, motion: bool):
        now = time.time()
        faces = face_result["faces"]
        count = face_result["count"]

        if count > 0:
            await fire_event("vision_addon.face_detected", {"count": count})

        person_states = {}
        for face in faces:
            name = face["name"]
            if name == "unknown":
                last = self._person_fired_at.get("unknown", 0)
                if now - last > 30:
                    self._person_fired_at["unknown"] = now
                    await fire_event("vision_addon.unknown_person", {})
            else:
                person_states[name] = True
                last = self._person_fired_at.get(name, 0)
                if now - last > 30:
                    self._person_fired_at[name] = now
                    await fire_event(
                        "vision_addon.person_identified",
                        {"name": name, "friendly_name": name},
                    )

        # Mark undetected known people as absent
        for name in self.face_engine.list_known():
            if name not in person_states:
                person_states[name] = False

        self.known_persons = person_states

        motion_on = False
        if motion:
            last_motion = self._motion_fired_at
            if now - last_motion > MOTION_COOLDOWN:
                self._motion_fired_at = now
                motion_on = True
                await fire_event("vision_addon.motion_detected", {})

        await update_sensors(count, person_states, motion_on)

    async def run(self):
        if STREAM_URL.startswith("/dev/video"):
            source = int(STREAM_URL.replace("/dev/video", "") or "0")
        else:
            source = STREAM_URL  # RTSP or other URL

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error(f"Cannot open stream: {STREAM_URL}")
            return

        if isinstance(source, int):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        else:
            # For RTSP: minimise buffer to reduce latency
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        interval = 1.0 / DETECTION_FPS
        self.running = True
        logger.info(f"Vision loop started at {DETECTION_FPS} FPS")

        while self.running:
            loop_start = time.time()
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame")
                await asyncio.sleep(interval)
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            motion = self._detect_motion(gray)
            face_result = self.face_engine.process_frame(frame_rgb)
            gesture = self.gesture_engine.process_frame(frame_rgb)

            await self._handle_gesture(gesture)
            await self._handle_faces(face_result, motion)

            # Encode JPEG for web stream
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            with self.frame_lock:
                self.latest_frame = jpeg.tobytes()
                self.latest_faces = face_result["faces"]
                self.latest_gesture = gesture

            elapsed = time.time() - loop_start
            await asyncio.sleep(max(0, interval - elapsed))

        cap.release()
        self.gesture_engine.close()


async def main():
    vision = VisionLoop()
    app = create_app(vision)

    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)

    await asyncio.gather(
        vision.run(),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
