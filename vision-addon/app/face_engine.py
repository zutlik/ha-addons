import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


class FaceEngine:
    def __init__(self, confidence_threshold: float = 0.6):
        self.threshold = confidence_threshold
        # Known-face registry kept as stubs — identification requires dlib/deepface
        # which are too heavy for the Pi. Presence counting still works.
        self._known: list = []

    def register_face(self, name: str, image_bytes: bytes) -> bool:
        if name not in self._known:
            self._known.append(name)
        logger.info(f"Registered face slot for {name} (detection only, no recognition)")
        return True

    def remove_face(self, name: str) -> bool:
        if name in self._known:
            self._known.remove(name)
            return True
        return False

    def list_known(self) -> list:
        return list(self._known)

    def process_frame(self, frame_rgb: np.ndarray) -> dict:
        gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
        faces = _CASCADE.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )
        results = []
        for (x, y, w, h) in (faces if len(faces) else []):
            results.append({
                "name": "unknown",
                "location": [y, x + w, y + h, x],  # top, right, bottom, left
            })
        return {"count": len(results), "faces": results}
