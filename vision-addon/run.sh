#!/bin/bash
set -e

get_opt() {
    jq -r ".${1} // \"${2}\"" /data/options.json 2>/dev/null || echo "${2}"
}

export STREAM_URL=$(get_opt stream_url "rtsp://10.100.102.15/live")
export DETECTION_FPS=$(get_opt detection_fps 5)
export FACE_CONFIDENCE=$(get_opt face_confidence 0.6)
export GESTURE_CONFIDENCE=$(get_opt gesture_confidence 0.7)
export GESTURE_COOLDOWN=$(get_opt gesture_cooldown_seconds 2)
export MOTION_COOLDOWN=$(get_opt motion_cooldown_seconds 5)
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://homeassistant:8123"
export MEDIAPIPE_DISABLE_GPU=1

echo "[vision-addon] Starting..."
echo "[vision-addon] Stream: ${STREAM_URL}"
echo "[vision-addon] FPS: ${DETECTION_FPS}"

cd /app
exec python3 main.py
