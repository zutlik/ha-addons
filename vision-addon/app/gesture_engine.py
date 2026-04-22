import logging
import numpy as np
import mediapipe as mp

logger = logging.getLogger(__name__)

# Finger tip and pip landmark indices
TIPS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky
PIPS = [3, 6, 10, 14, 18]


class GestureEngine:
    def __init__(self, confidence_threshold: float = 0.7):
        self.threshold = confidence_threshold
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=confidence_threshold,
            min_tracking_confidence=0.5,
        )

    def _fingers_up(self, landmarks) -> list:
        fingers = []
        # Thumb: compare x (flipped for right hand)
        fingers.append(1 if landmarks[TIPS[0]].x < landmarks[PIPS[0]].x else 0)
        # Other fingers: tip y < pip y means extended
        for i in range(1, 5):
            fingers.append(1 if landmarks[TIPS[i]].y < landmarks[PIPS[i]].y else 0)
        return fingers

    def _classify(self, landmarks) -> str | None:
        lm = landmarks
        f = self._fingers_up(lm)
        total = sum(f)

        # Helpers
        def tip(i):
            return lm[TIPS[i]]

        def base(i):
            return lm[PIPS[i]]

        # Thumbs up: only thumb up, others closed
        if f == [1, 0, 0, 0, 0]:
            # thumb points up (y decreasing upward)
            if lm[4].y < lm[3].y < lm[2].y:
                return "thumbs_up"
            else:
                return "thumbs_down"

        # Thumbs down: only thumb extended downward
        if f == [1, 0, 0, 0, 0]:
            if lm[4].y > lm[3].y:
                return "thumbs_down"

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
        result = self.hands.process(frame_rgb)
        if not result.multi_hand_landmarks:
            return None
        landmarks = result.multi_hand_landmarks[0].landmark
        return self._classify(landmarks)

    def close(self):
        self.hands.close()
