import os
import pickle
import logging
import numpy as np
import face_recognition
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_FACES_DIR = Path("/data/known_faces")
ENCODINGS_FILE = KNOWN_FACES_DIR / "encodings.pkl"


class FaceEngine:
    def __init__(self, confidence_threshold: float = 0.6):
        self.threshold = confidence_threshold
        self.known_encodings: list = []
        self.known_names: list = []
        self._load_encodings()

    def _load_encodings(self):
        if ENCODINGS_FILE.exists():
            with open(ENCODINGS_FILE, "rb") as f:
                data = pickle.load(f)
                self.known_encodings = data.get("encodings", [])
                self.known_names = data.get("names", [])
            logger.info(f"Loaded {len(self.known_names)} known faces")
        else:
            logger.info("No known faces found, starting fresh")

    def _save_encodings(self):
        KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)
        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump({"encodings": self.known_encodings, "names": self.known_names}, f)

    def register_face(self, name: str, image_bytes: bytes) -> bool:
        import PIL.Image
        import io
        image = PIL.Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(image)
        encodings = face_recognition.face_encodings(img_array)
        if not encodings:
            logger.warning(f"No face found in image for {name}")
            return False
        self.known_encodings.append(encodings[0])
        self.known_names.append(name)
        self._save_encodings()
        logger.info(f"Registered face for {name}")
        return True

    def remove_face(self, name: str) -> bool:
        indices = [i for i, n in enumerate(self.known_names) if n == name]
        if not indices:
            return False
        for i in reversed(indices):
            self.known_encodings.pop(i)
            self.known_names.pop(i)
        self._save_encodings()
        return True

    def list_known(self) -> list:
        return list(set(self.known_names))

    def process_frame(self, frame_rgb: np.ndarray) -> dict:
        small = frame_rgb[::2, ::2]  # half resolution for speed
        locations = face_recognition.face_locations(small, model="hog")
        encodings = face_recognition.face_encodings(small, locations)

        results = []
        for encoding, location in zip(encodings, locations):
            name = "unknown"
            if self.known_encodings:
                distances = face_recognition.face_distance(self.known_encodings, encoding)
                best_idx = int(np.argmin(distances))
                if distances[best_idx] < (1.0 - self.threshold):
                    name = self.known_names[best_idx]
            # scale location back up
            top, right, bottom, left = [v * 2 for v in location]
            results.append({"name": name, "location": [top, right, bottom, left]})

        return {"count": len(results), "faces": results}
