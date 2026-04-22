#!/usr/bin/with-contenv bashio

export VIDEO_DEVICE=$(bashio::config 'video_device')
export DETECTION_FPS=$(bashio::config 'detection_fps')
export FACE_CONFIDENCE=$(bashio::config 'face_confidence')
export GESTURE_CONFIDENCE=$(bashio::config 'gesture_confidence')
export GESTURE_COOLDOWN=$(bashio::config 'gesture_cooldown_seconds')
export MOTION_COOLDOWN=$(bashio::config 'motion_cooldown_seconds')
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"

bashio::log.info "Starting Vision Addon..."
bashio::log.info "Video device: ${VIDEO_DEVICE}"
bashio::log.info "Detection FPS: ${DETECTION_FPS}"

cd /app
exec python3 main.py
