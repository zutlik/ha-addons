import asyncio
import os
import time
import logging
import threading
import urllib.parse
import numpy as np

# Must be set before cv2 is imported so ffmpeg uses TCP for RTSP.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
import cv2

from gesture_engine import GestureEngine
from ha_client import close_session, fire_event, set_last_gesture, update_sensors
from dhcp_discovery import DHCPDiscoveryError, resolve_hostname_ip
from web_ui import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# --- Stream source ---
# STREAM_URL: optional override. If set, used as-is and DHCP discovery is skipped.
# Otherwise CAMERA_HOSTNAME is resolved via HA's DHCP discovery WebSocket.
STREAM_URL = os.environ.get("STREAM_URL", "").strip()
CAMERA_HOSTNAME = os.environ.get("CAMERA_HOSTNAME", "").strip()
CAMERA_USER = os.environ.get("CAMERA_USER", "").strip()
CAMERA_PASSWORD = os.environ.get("CAMERA_PASSWORD", "")
RTSP_PATH = os.environ.get("RTSP_PATH", "/h264Preview_01_sub")
RTSP_PORT = int(os.environ.get("RTSP_PORT", "554"))
HA_URL = os.environ.get("HA_URL", "http://homeassistant:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "").strip()
DISCOVERY_TIMEOUT_SECONDS = float(os.environ.get("DISCOVERY_TIMEOUT_SECONDS", "60"))
STARTUP_ATTEMPTS_FILE = os.environ.get("STARTUP_ATTEMPTS_FILE", "/data/.startup_attempts")

DETECTION_FPS = max(1, int(os.environ.get("DETECTION_FPS", "10")))
ENABLE_FACE_DETECTION = _env_bool("ENABLE_FACE_DETECTION", False)
FACE_CONFIDENCE = float(os.environ.get("FACE_CONFIDENCE", "0.6"))
FACE_DETECTION_INTERVAL = max(0.1, float(os.environ.get("FACE_DETECTION_INTERVAL", "3.0")))
GESTURE_CONFIDENCE = float(os.environ.get("GESTURE_CONFIDENCE", "0.55"))
GESTURE_TRACKING_CONFIDENCE = float(os.environ.get("GESTURE_TRACKING_CONFIDENCE", "0.5"))
GESTURE_MODEL_COMPLEXITY = int(os.environ.get("GESTURE_MODEL_COMPLEXITY", "0"))
GESTURE_COOLDOWN = float(os.environ.get("GESTURE_COOLDOWN", "1.2"))
GESTURE_HOLD_SECONDS = max(0.1, float(os.environ.get("GESTURE_HOLD_SECONDS", "0.2")))
GESTURE_MISS_GRACE_SECONDS = max(0.0, float(os.environ.get("GESTURE_MISS_GRACE_SECONDS", "0.35")))
GESTURE_MIN_FRAMES = max(1, int(os.environ.get("GESTURE_MIN_FRAMES", "2")))
MOTION_COOLDOWN = float(os.environ.get("MOTION_COOLDOWN", "5"))
CAMERA_WIDTH = max(160, int(os.environ.get("CAMERA_WIDTH", "640")))
CAMERA_HEIGHT = max(120, int(os.environ.get("CAMERA_HEIGHT", "480")))
PROCESSING_WIDTH = max(0, int(os.environ.get("PROCESSING_WIDTH", "320")))
JPEG_QUALITY = min(95, max(30, int(os.environ.get("JPEG_QUALITY", "65"))))


def _build_rtsp_url(ip: str) -> str:
    user = urllib.parse.quote(CAMERA_USER, safe="")
    pw = urllib.parse.quote(CAMERA_PASSWORD, safe="")
    path = RTSP_PATH if RTSP_PATH.startswith("/") else "/" + RTSP_PATH
    return f"rtsp://{user}:{pw}@{ip}:{RTSP_PORT}{path}"


def _redact(url: str) -> str:
    """Strip credentials from URL for logging."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.username or parsed.password:
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc += f":{parsed.port}"
            return urllib.parse.urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return url


def _reset_startup_attempts() -> None:
    try:
        with open(STARTUP_ATTEMPTS_FILE, "w") as f:
            f.write("0")
    except OSError as e:
        logger.warning("Could not reset startup attempts file: %s", e)


RECOVERY_INTERVAL_SECONDS = 30.0
# Frames of consecutive read failures before we declare the stream unhealthy
# and try recovery. At 10 FPS this is ~3 seconds.
UNHEALTHY_FAILURE_THRESHOLD = 30


class VisionLoop:
    def __init__(self, initial_stream_url: str, recover=None):
        """``recover`` is an optional async callable that returns a fresh stream
        URL (or None to keep the current one) when the loop asks for recovery.
        """
        self.face_engine = None
        if ENABLE_FACE_DETECTION:
            from face_engine import FaceEngine

            self.face_engine = FaceEngine(FACE_CONFIDENCE)

        self.gesture_engine = GestureEngine(
            GESTURE_CONFIDENCE,
            tracking_confidence=GESTURE_TRACKING_CONFIDENCE,
            model_complexity=GESTURE_MODEL_COMPLEXITY,
        )
        self.running = False
        self._stream_url = initial_stream_url
        self._recover = recover
        self._first_frame_seen = False

        # Stream-health tracking
        self._consecutive_failures = 0
        self._last_recovery_attempt = 0.0

        # Shared state for web UI
        self.latest_frame: bytes = b""
        self.latest_faces: list = []
        self.latest_gesture: str | None = None
        self.known_persons: dict = {}  # name -> currently detected bool
        self.frame_lock = threading.Lock()

        # Gesture hold tracking
        self._gesture_candidate: str | None = None
        self._gesture_start: float = 0.0
        self._gesture_last_seen: float = 0.0
        self._gesture_observations: int = 0
        self._gesture_fired_at: float = 0.0  # last time we fired this gesture

        # Motion tracking
        self._prev_gray = None
        self._motion_fired_at: float = 0.0

        # Face cooldown per person
        self._person_fired_at: dict = {}
        self._last_face_result = {"count": 0, "faces": []}
        self._last_face_processed_at: float = 0.0

    def _processing_frame(self, frame_rgb: np.ndarray) -> np.ndarray:
        if PROCESSING_WIDTH <= 0 or frame_rgb.shape[1] <= PROCESSING_WIDTH:
            return frame_rgb
        scale = PROCESSING_WIDTH / frame_rgb.shape[1]
        height = max(1, int(frame_rgb.shape[0] * scale))
        return cv2.resize(frame_rgb, (PROCESSING_WIDTH, height), interpolation=cv2.INTER_AREA)

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
            if self._gesture_candidate and now - self._gesture_last_seen <= GESTURE_MISS_GRACE_SECONDS:
                return
            self._reset_gesture_candidate()
            return

        if gesture != self._gesture_candidate:
            self._gesture_candidate = gesture
            self._gesture_start = now
            self._gesture_last_seen = now
            self._gesture_observations = 1
            return

        self._gesture_last_seen = now
        self._gesture_observations += 1
        held_for = now - self._gesture_start
        if held_for < GESTURE_HOLD_SECONDS or self._gesture_observations < GESTURE_MIN_FRAMES:
            return

        # Gesture held long enough — check cooldown
        last_fired = self._gesture_fired_at
        if now - last_fired < GESTURE_COOLDOWN:
            return

        self._gesture_fired_at = now
        self._reset_gesture_candidate()

        logger.info(f"Gesture fired: {gesture}")
        await fire_event("vision_addon.gesture_detected", {"gesture": gesture})
        await set_last_gesture(gesture)

    def _reset_gesture_candidate(self):
        self._gesture_candidate = None
        self._gesture_start = 0.0
        self._gesture_last_seen = 0.0
        self._gesture_observations = 0

    async def _handle_faces(self, face_result: dict, motion: bool, faces_fresh: bool):
        now = time.time()
        faces = face_result["faces"]
        count = face_result["count"]

        if faces_fresh and count > 0:
            await fire_event("vision_addon.face_detected", {"count": count})

        person_states = {}
        if self.face_engine is not None:
            for face in faces:
                name = face["name"]
                if name == "unknown":
                    last = self._person_fired_at.get("unknown", 0)
                    if faces_fresh and now - last > 30:
                        self._person_fired_at["unknown"] = now
                        await fire_event("vision_addon.unknown_person", {})
                else:
                    person_states[name] = True
                    last = self._person_fired_at.get(name, 0)
                    if faces_fresh and now - last > 30:
                        self._person_fired_at[name] = now
                        await fire_event(
                            "vision_addon.person_identified",
                            {"name": name, "friendly_name": name},
                        )

            # Mark undetected known people as absent.
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

    def _open_capture(self) -> cv2.VideoCapture | None:
        url = self._stream_url
        if url.startswith("/dev/video"):
            source = int(url.replace("/dev/video", "") or "0")
        else:
            source = url

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error("Cannot open stream: %s", _redact(url))
            return None

        if isinstance(source, int):
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, max(DETECTION_FPS, 10))

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    async def _attempt_recovery(self, cap: cv2.VideoCapture) -> cv2.VideoCapture:
        """Re-resolve the stream URL (if a recover callback was provided) and
        reopen the capture. Always reopens, even if the URL is unchanged —
        this also recovers from transient RTSP drops at the same IP. Never
        raises; returns a (possibly closed) capture object."""
        logger.info(
            "Attempting recovery (failed frames=%d, current=%s)",
            self._consecutive_failures,
            _redact(self._stream_url),
        )
        if self._recover is not None:
            try:
                new_url = await self._recover()
            except Exception as e:
                logger.warning("Recovery callback failed: %s", e)
                new_url = None
            if new_url and new_url != self._stream_url:
                logger.info("Stream URL updated: %s", _redact(new_url))
                self._stream_url = new_url
        cap.release()
        new_cap = self._open_capture()
        if new_cap is None:
            logger.warning(
                "Capture reopen failed; will retry in %.0fs",
                RECOVERY_INTERVAL_SECONDS,
            )
            # Return a closed cap; the loop's read() will keep failing and
            # _last_recovery_attempt throttles the next try.
            return cap
        return new_cap

    async def run(self):
        cap = self._open_capture()
        if cap is None:
            return

        interval = 1.0 / DETECTION_FPS
        self.running = True
        logger.info(
            "Vision loop started at %s FPS, face detection %s, processing width %s, source=%s",
            DETECTION_FPS,
            "enabled" if self.face_engine is not None else "disabled",
            PROCESSING_WIDTH,
            _redact(self._stream_url),
        )
        await set_last_gesture("none")  # ensure entity exists from startup

        try:
            while self.running:
                loop_start = time.time()
                ret, frame = cap.read()
                if not ret:
                    self._consecutive_failures += 1
                    if self._consecutive_failures == 1:
                        logger.warning("Stream stalled (frame read failed)")

                    now = time.time()
                    if (
                        self._consecutive_failures >= UNHEALTHY_FAILURE_THRESHOLD
                        and now - self._last_recovery_attempt >= RECOVERY_INTERVAL_SECONDS
                    ):
                        self._last_recovery_attempt = now
                        cap = await self._attempt_recovery(cap)

                    await asyncio.sleep(interval)
                    continue

                if self._consecutive_failures:
                    logger.info(
                        "Stream recovered after %d failed frame reads",
                        self._consecutive_failures,
                    )
                    self._consecutive_failures = 0

                if not self._first_frame_seen:
                    self._first_frame_seen = True
                    _reset_startup_attempts()
                    logger.info("First frame captured — startup retry counter reset.")

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                processing_rgb = self._processing_frame(frame_rgb)
                gray = cv2.cvtColor(processing_rgb, cv2.COLOR_RGB2GRAY)

                motion = self._detect_motion(gray)
                gesture = self.gesture_engine.process_frame(processing_rgb)

                face_result = self._last_face_result
                faces_fresh = False
                if self.face_engine is not None:
                    now = time.time()
                    if now - self._last_face_processed_at >= FACE_DETECTION_INTERVAL:
                        face_result = self.face_engine.process_frame(processing_rgb)
                        self._last_face_result = face_result
                        self._last_face_processed_at = now
                        faces_fresh = True

                await self._handle_gesture(gesture)
                await self._handle_faces(face_result, motion, faces_fresh)

                # Encode JPEG for web stream.
                _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                with self.frame_lock:
                    self.latest_frame = jpeg.tobytes()
                    self.latest_faces = face_result["faces"]
                    self.latest_gesture = gesture

                elapsed = time.time() - loop_start
                await asyncio.sleep(max(0, interval - elapsed))
        finally:
            cap.release()
            self.gesture_engine.close()


def _validate_discovery_config() -> None:
    if not CAMERA_HOSTNAME:
        raise RuntimeError(
            "No stream source configured: set either stream_url or camera_hostname."
        )
    if not HA_TOKEN:
        raise RuntimeError(
            "ha_token is required for DHCP discovery (Long-Lived Access Token from "
            "HA → Profile → Security)."
        )
    if not CAMERA_USER or not CAMERA_PASSWORD:
        raise RuntimeError(
            "camera_user and camera_password are required when using DHCP discovery."
        )


async def _resolve_initial_stream_url() -> str:
    """Resolve the initial stream URL at startup, raising RuntimeError on
    misconfiguration. STREAM_URL override skips discovery entirely."""
    if STREAM_URL:
        logger.info("Using STREAM_URL override: %s", _redact(STREAM_URL))
        return STREAM_URL

    _validate_discovery_config()
    try:
        ip = await resolve_hostname_ip(
            HA_URL, HA_TOKEN, CAMERA_HOSTNAME, timeout=DISCOVERY_TIMEOUT_SECONDS,
        )
    except DHCPDiscoveryError as e:
        raise RuntimeError(f"DHCP discovery failed: {e}") from e
    return _build_rtsp_url(ip)


async def _recovery_resolve() -> str | None:
    """Recovery callback: re-resolve hostname → fresh RTSP URL. Returns None
    on failure so the vision loop can still reopen with its current URL."""
    if STREAM_URL or not CAMERA_HOSTNAME:
        return None
    try:
        ip = await resolve_hostname_ip(HA_URL, HA_TOKEN, CAMERA_HOSTNAME, timeout=10.0)
    except DHCPDiscoveryError as e:
        logger.warning("Recovery DHCP resolve failed: %s", e)
        return None
    return _build_rtsp_url(ip)


async def main():
    stream_url = await _resolve_initial_stream_url()
    recover = _recovery_resolve if not STREAM_URL else None
    vision = VisionLoop(initial_stream_url=stream_url, recover=recover)
    app = create_app(vision)

    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)

    try:
        await asyncio.gather(vision.run(), server.serve())
    finally:
        await close_session()


if __name__ == "__main__":
    asyncio.run(main())
