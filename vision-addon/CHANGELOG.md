## 1.2.0

- **Camera IP auto-discovery via HA's DHCP integration.** Configure the
  camera's hostname (as seen on `/config/dhcp`) instead of a hard-coded URL.
  The addon resolves the hostname to a current IP at startup and reconnects
  automatically when the IP changes — no addon restart required.
- New required option: `ha_token` (Long-Lived Access Token from HA → Profile
  → Security). Used for both the DHCP WebSocket subscription and writing
  events/sensors back to HA. Must be created by an admin user.
- New options: `camera_hostname`, `camera_user`, `camera_password`,
  `rtsp_path`, `rtsp_port`. The legacy `stream_url` option is retained as an
  optional override; if set, it bypasses discovery entirely.
- Removed the supervisor token path. `homeassistant_api: true` is no longer
  needed; all HA API access flows through the LLAT against
  `http://homeassistant:8123`.
- Startup hardening: 60-second timeout per attempt; supervisor restarts on
  failure; capped at 3 consecutive failures via a counter file in `/data`.
- `restart_policy` changed from `unless-stopped` to `on-failure` so the
  retry cap actually takes effect.

## 1.1.8

- Lowered default `gesture_hold_seconds` (0.6 → 0.2) and `gesture_min_frames` (3 → 2) for faster initial recognition.
- Lowered default `gesture_cooldown_seconds` (2 → 1.2) so a held gesture retriggers at a steady pace.
- Changed `gesture_cooldown_seconds` schema from `int` to `float` so sub-second cooldowns are allowed.

## 1.1.7

- Disabled face detection by default so gesture recognition owns the fast path.
- Added optional scheduled face detection for users who still want face events.
- Reduced gesture latency with a shorter hold time, missed-frame grace, faster MediaPipe hand model, and lower processing resolution.
- Reused Home Assistant API sessions and skipped unchanged sensor updates to avoid per-frame HTTP overhead.

## 1.0.0

- Initial release
- Face detection and recognition via face_recognition (dlib)
- Gesture detection (10 gestures) via MediaPipe Hands
- Gesture hold requirement: 1.5 seconds continuous hold before firing
- Motion detection
- HA events: vision_addon.face_detected, vision_addon.person_identified, vision_addon.gesture_detected, vision_addon.unknown_person, vision_addon.motion_detected
- HA sensors: sensor.vision_faces_count, binary_sensor.vision_motion, binary_sensor.vision_person_<name>
- Web UI with live stream, face registration, gesture display
