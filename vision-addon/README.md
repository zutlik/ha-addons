# Vision Addon

Camera-based gesture, face, and motion detection for Home Assistant. Reads
an RTSP stream (typically a Reolink/Lynx-class IP camera) or a local webcam,
publishes detection events and sensors back to HA, and exposes a small web
UI for live preview and face registration.

## Configuration

The addon supports two ways to point at the camera:

1. **Hostname-based discovery (recommended)** — set `camera_hostname` and
   credentials. The addon resolves the hostname to a current IP via HA's
   built-in DHCP discovery and reconnects automatically when the IP changes.
2. **Direct URL (fallback)** — set `stream_url` to a fully-qualified RTSP
   URL or a `/dev/video*` path. Discovery is skipped.

### Required for hostname-based discovery

| Option | Where to find it |
|---|---|
| `ha_token` | HA → your profile (top-left avatar) → Security tab → "Long-Lived Access Tokens" → **Create Token**. Must be created by an admin user — `dhcp/subscribe_discovery` requires admin scope. |
| `camera_hostname` | HA → Settings → Devices & Services → click **Discovered** or open `/config/dhcp`. Find your camera's row and copy the hostname (e.g. `Lynx`). |
| `camera_user` / `camera_password` | The RTSP credentials configured on the camera itself (Reolink: User Management → admin). |
| `rtsp_path` | Reolink defaults to `/h264Preview_01_sub` (sub stream) or `/h264Preview_01_main`. Other vendors vary — check the camera manual. |
| `rtsp_port` | Default `554`. |

### Stream URL fallback

If you'd rather not depend on HA's DHCP integration (or your camera has a
static IP outside the DHCP table), put the full URL into `stream_url`:

```
rtsp://admin:secret@10.0.0.20:554/h264Preview_01_sub
```

When `stream_url` is set, all hostname/credential fields are ignored.

## Startup behavior

- The addon waits up to **60 seconds** for `camera_hostname` to appear in
  HA's DHCP discovery.
- If the hostname doesn't appear, or the WebSocket connection fails, the
  addon exits non-zero and the supervisor restarts it.
- After **3 consecutive failed startups**, the addon stops itself rather
  than looping forever. Fix the configuration and start the addon manually
  from the HA UI to reset the counter.
- Once the first frame is captured, the retry counter is reset to 0.

## Events and sensors

| Event | Data |
|---|---|
| `vision_addon.gesture_detected` | `{"gesture": "<name>"}` — fires whenever a gesture is confirmed |
| `vision_addon.face_detected` | `{"count": N}` |
| `vision_addon.person_identified` | `{"name": "..."}` |
| `vision_addon.unknown_person` | `{}` |
| `vision_addon.motion_detected` | `{}` |

| Entity | Purpose |
|---|---|
| `sensor.vision_last_gesture` | Most recent gesture name |
| `sensor.vision_faces_count` | Currently visible face count |
| `binary_sensor.vision_motion` | Motion within the cooldown window |
| `binary_sensor.vision_person_<name>` | Whether a registered person is currently visible |

For automations that need to retrigger while the same gesture is held, use
the **event** (`vision_addon.gesture_detected`), not the sensor — the sensor
only changes when the gesture changes.
