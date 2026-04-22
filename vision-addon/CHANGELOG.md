## 1.0.0

- Initial release
- Face detection and recognition via face_recognition (dlib)
- Gesture detection (10 gestures) via MediaPipe Hands
- Gesture hold requirement: 1.5 seconds continuous hold before firing
- Motion detection
- HA events: vision_addon.face_detected, vision_addon.person_identified, vision_addon.gesture_detected, vision_addon.unknown_person, vision_addon.motion_detected
- HA sensors: sensor.vision_faces_count, binary_sensor.vision_motion, binary_sensor.vision_person_<name>
- Web UI with live stream, face registration, gesture display
