#!/bin/bash
set -e

get_opt() {
    jq -r ".${1} // \"${2}\"" /data/options.json 2>/dev/null || echo "${2}"
}

export STREAM_URL=$(get_opt stream_url "rtsp://10.100.102.15/live")
export DETECTION_FPS=$(get_opt detection_fps 10)
export ENABLE_FACE_DETECTION=$(get_opt enable_face_detection false)
export FACE_CONFIDENCE=$(get_opt face_confidence 0.6)
export FACE_DETECTION_INTERVAL=$(get_opt face_detection_interval_seconds 3.0)
export GESTURE_CONFIDENCE=$(get_opt gesture_confidence 0.55)
export GESTURE_TRACKING_CONFIDENCE=$(get_opt gesture_tracking_confidence 0.5)
export GESTURE_MODEL_COMPLEXITY=$(get_opt gesture_model_complexity 0)
export GESTURE_COOLDOWN=$(get_opt gesture_cooldown_seconds 2)
export GESTURE_HOLD_SECONDS=$(get_opt gesture_hold_seconds 0.6)
export GESTURE_MISS_GRACE_SECONDS=$(get_opt gesture_miss_grace_seconds 0.35)
export GESTURE_MIN_FRAMES=$(get_opt gesture_min_frames 3)
export MOTION_COOLDOWN=$(get_opt motion_cooldown_seconds 5)
export CAMERA_WIDTH=$(get_opt camera_width 640)
export CAMERA_HEIGHT=$(get_opt camera_height 480)
export PROCESSING_WIDTH=$(get_opt processing_width 320)
export JPEG_QUALITY=$(get_opt jpeg_quality 65)
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"
export MEDIAPIPE_DISABLE_GPU=1

echo "[vision-addon] Starting..."
echo "[vision-addon] Stream: ${STREAM_URL}"
echo "[vision-addon] FPS: ${DETECTION_FPS}"
echo "[vision-addon] Face detection: ${ENABLE_FACE_DETECTION}"
echo "[vision-addon] Processing width: ${PROCESSING_WIDTH}"

cd /app
exec python3 main.py
