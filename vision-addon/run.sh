#!/bin/bash
# Wrapper that runs the vision addon entrypoint with a startup-retry guard.
#
# HA Supervisor doesn't support `restart_policy: on-failure:max_retries`, so
# we enforce a 3-attempt cap ourselves via a counter file in /data. The
# Python entrypoint resets the counter to 0 once it captures its first frame
# (i.e. the camera came up). After 3 consecutive startup failures, we exit
# cleanly so the supervisor stops restarting; the counter is reset at that
# point so a subsequent manual start begins fresh.
set -e

get_opt() {
    jq -r ".${1} // \"${2}\"" /data/options.json 2>/dev/null || echo "${2}"
}

# Stream source — DHCP discovery path
export HA_TOKEN=$(get_opt ha_token "")
export CAMERA_HOSTNAME=$(get_opt camera_hostname "")
export CAMERA_USER=$(get_opt camera_user "")
export CAMERA_PASSWORD=$(get_opt camera_password "")
export RTSP_PATH=$(get_opt rtsp_path "/h264Preview_01_sub")
export RTSP_PORT=$(get_opt rtsp_port 554)
# Optional override. If set, used as-is and DHCP discovery is skipped.
export STREAM_URL=$(get_opt stream_url "")

# Detection settings
export DETECTION_FPS=$(get_opt detection_fps 10)
export ENABLE_FACE_DETECTION=$(get_opt enable_face_detection false)
export FACE_CONFIDENCE=$(get_opt face_confidence 0.6)
export FACE_DETECTION_INTERVAL=$(get_opt face_detection_interval_seconds 3.0)
export GESTURE_CONFIDENCE=$(get_opt gesture_confidence 0.55)
export GESTURE_TRACKING_CONFIDENCE=$(get_opt gesture_tracking_confidence 0.5)
export GESTURE_MODEL_COMPLEXITY=$(get_opt gesture_model_complexity 0)
export GESTURE_COOLDOWN=$(get_opt gesture_cooldown_seconds 1.2)
export GESTURE_HOLD_SECONDS=$(get_opt gesture_hold_seconds 0.2)
export GESTURE_MISS_GRACE_SECONDS=$(get_opt gesture_miss_grace_seconds 0.35)
export GESTURE_MIN_FRAMES=$(get_opt gesture_min_frames 2)
export MOTION_COOLDOWN=$(get_opt motion_cooldown_seconds 5)
export CAMERA_WIDTH=$(get_opt camera_width 640)
export CAMERA_HEIGHT=$(get_opt camera_height 480)
export PROCESSING_WIDTH=$(get_opt processing_width 320)
export JPEG_QUALITY=$(get_opt jpeg_quality 65)

# All HA API access (REST + WebSocket) uses the user-provided LLAT against
# the HA core directly. The supervisor token path is intentionally not used.
export HA_URL="http://homeassistant:8123"
export MEDIAPIPE_DISABLE_GPU=1

COUNTER_FILE=/data/.startup_attempts
MAX_ATTEMPTS=3
COUNT=$(cat "$COUNTER_FILE" 2>/dev/null || echo 0)
case "$COUNT" in ''|*[!0-9]*) COUNT=0 ;; esac

if [ "$COUNT" -ge "$MAX_ATTEMPTS" ]; then
    echo "[vision-addon] Reached max startup attempts (${MAX_ATTEMPTS}). Stopping."
    echo "[vision-addon] To retry, fix the configuration and start the addon again."
    rm -f "$COUNTER_FILE"
    exit 0
fi

NEXT=$((COUNT + 1))
echo "$NEXT" > "$COUNTER_FILE"

echo "[vision-addon] Starting (attempt ${NEXT}/${MAX_ATTEMPTS})..."
if [ -n "$STREAM_URL" ]; then
    echo "[vision-addon] Stream source: STREAM_URL override"
elif [ -n "$CAMERA_HOSTNAME" ]; then
    echo "[vision-addon] Stream source: DHCP discovery for hostname '${CAMERA_HOSTNAME}'"
else
    echo "[vision-addon] ERROR: neither stream_url nor camera_hostname is configured."
fi
echo "[vision-addon] FPS: ${DETECTION_FPS}, face detection: ${ENABLE_FACE_DETECTION}, processing width: ${PROCESSING_WIDTH}"

cd /app
exec python3 main.py
