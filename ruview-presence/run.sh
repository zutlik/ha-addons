#!/usr/bin/env bash
set -e

# ── Install HA sensor package ─────────────────────────────────────────────────
# Maps to /config inside the container when config:rw is set in addon config.
# Creates /config/packages/ruview.yaml so HA auto-loads the sensors on restart.
if [ -d "/config" ]; then
    mkdir -p /config/packages
    cp /tmp/ruview_ha_package.yaml /config/packages/ruview.yaml
    echo "[RuView] Sensor package written to /config/packages/ruview.yaml"
    echo "[RuView] Restart Home Assistant once to load the sensors."
else
    echo "[RuView] WARNING: /config not mounted, skipping sensor package install."
fi

# ── Start the RuView server ───────────────────────────────────────────────────
# Try known binary locations in order (sensing_server seen in container logs).
for bin in sensing_server wifi-densepose sensing-server server; do
    if command -v "$bin" &>/dev/null; then
        echo "[RuView] Starting: $bin"
        exec "$bin"
    fi
done

# Fallback: scan common paths
for path in /usr/local/bin/sensing_server /app/sensing_server /app/server /usr/local/bin/server; do
    if [ -x "$path" ]; then
        echo "[RuView] Starting: $path"
        exec "$path"
    fi
done

echo "[RuView] ERROR: Could not find server binary. Check the image."
exit 1
