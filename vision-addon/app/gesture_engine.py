import logging
import numpy as np
import mediapipe as mp

logger = logging.getLogger(__name__)

# Finger tip and pip landmark indices
TIPS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky
PIPS = [3, 6, 10, 14, 18]


class GestureEngine:
    def __init__(
        self,
        confidence_threshold: float = 0.55,
        tracking_confidence: float = 0.5,
        model_complexity: int = 0,
    ):
        self.threshold = confidence_threshold
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=model_complexity,
            min_detection_confidence=confidence_threshold,
            min_tracking_confidence=tracking_confidence,
        )

    @staticmethod
    def _dist(a, b) -> float:
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5

    def _fingers_up(self, landmarks, handedness: str | None = None) -> list:
        fingers = []
        wrist = landmarks[0]

        # Thumb extension is side-dependent. MediaPipe's handedness can be off
        # with non-selfie cameras, so fall back to a palm-distance check too.
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        index_mcp = landmarks[5]
        if handedness == "Left":
            thumb_side_open = thumb_tip.x > thumb_ip.x
        else:
            thumb_side_open = thumb_tip.x < thumb_ip.x
        thumb_away_from_palm = (
            self._dist(thumb_tip, index_mcp) > self._dist(thumb_ip, index_mcp) * 1.08
        )
        thumb_from_wrist = (
            self._dist(thumb_tip, wrist) > self._dist(thumb_mcp, wrist) * 0.95
        )
        fingers.append(1 if (thumb_side_open or thumb_away_from_palm) and thumb_from_wrist else 0)

        # For the other fingers, wrist distance is more tolerant of hand rotation
        # than comparing y coordinates alone.
        for i in range(1, 5):
            tip = landmarks[TIPS[i]]
            pip = landmarks[PIPS[i]]
            fingers.append(1 if self._dist(tip, wrist) > self._dist(pip, wrist) * 1.08 else 0)
        return fingers

    def _classify(self, landmarks, handedness: str | None = None) -> str | None:
        lm = landmarks
        f = self._fingers_up(lm, handedness)
        total = sum(f)

        # Thumbs up: only thumb up, others closed
        if f == [1, 0, 0, 0, 0]:
            thumb_dx = abs(lm[4].x - lm[2].x)
            thumb_dy = lm[4].y - lm[2].y
            if thumb_dy < -max(0.04, thumb_dx * 0.45):
                return "thumbs_up"
            if thumb_dy > max(0.04, thumb_dx * 0.45):
                return "thumbs_down"
            return "thumbs_up"

        # Open palm: all 5 fingers up
        if total == 5:
            return "open_palm"

        # Fist: all fingers down
        if total == 0:
            return "fist"

        # Pointing up: only index up
        if f == [0, 1, 0, 0, 0]:
            return "pointing_up"

        # Peace: index + middle up
        if f == [0, 1, 1, 0, 0]:
            return "peace"

        # Rock on: index + pinky up
        if f == [0, 1, 0, 0, 1]:
            return "rock_on"

        # Shaka: thumb + pinky up
        if f == [1, 0, 0, 0, 1]:
            return "shaka"

        # OK: thumb + index close, others up
        if f[2] == 1 and f[3] == 1 and f[4] == 1:
            thumb_tip = lm[4]
            index_tip = lm[8]
            dist = ((thumb_tip.x - index_tip.x) ** 2 + (thumb_tip.y - index_tip.y) ** 2) ** 0.5
            if dist < 0.08:
                return "ok"

        # Five spread (same as open palm but we keep it)
        if total == 5:
            return "five_spread"

        # Finger count (1-5)
        if 1 <= total <= 5:
            return f"fingers_{total}"

        return None

    def process_frame(self, frame_rgb: np.ndarray) -> str | None:
        was_writeable = frame_rgb.flags.writeable
        frame_rgb.flags.writeable = False
        try:
            result = self.hands.process(frame_rgb)
        finally:
            frame_rgb.flags.writeable = was_writeable
        if not result.multi_hand_landmarks:
            return None
        landmarks = result.multi_hand_landmarks[0].landmark
        handedness = None
        if result.multi_handedness:
            handedness = result.multi_handedness[0].classification[0].label
        return self._classify(landmarks, handedness)

    def close(self):
        self.hands.close()
