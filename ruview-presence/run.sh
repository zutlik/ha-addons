#!/usr/bin/env bash
set -e

# ── 1. Drop the HA sensors package ───────────────────────────────────────────
mkdir -p /config/packages
cp /tmp/ruview_ha_package.yaml /config/packages/ruview.yaml
echo "[RuView] Sensor package written to /config/packages/ruview.yaml"

# ── 2. Ensure configuration.yaml loads the packages directory ────────────────
CONFIG="/config/configuration.yaml"

if grep -q "packages:" "$CONFIG" 2>/dev/null; then
    echo "[RuView] Packages already enabled in configuration.yaml — skipping."
elif grep -q "^homeassistant:" "$CONFIG" 2>/dev/null; then
    # homeassistant: block exists but has no packages: key.
    # Inject "  packages: !include_dir_named packages" on the line after it.
    sed -i '/^homeassistant:/a\  packages: !include_dir_named packages' "$CONFIG"
    echo "[RuView] Injected packages include under existing homeassistant: block."
else
    # No homeassistant: block at all — append one.
    cat >> "$CONFIG" << 'EOF'

# Added by RuView addon — loads /config/packages/*.yaml on HA startup
homeassistant:
  packages: !include_dir_named packages
EOF
    echo "[RuView] Appended homeassistant: packages block to configuration.yaml."
fi

echo "[RuView] Restart Home Assistant once to activate the sensors."

# ── 3. Start the RuView server ───────────────────────────────────────────────
for bin in sensing_server wifi-densepose sensing-server server; do
    if command -v "$bin" &>/dev/null; then
        echo "[RuView] Starting: $bin"
        exec "$bin"
    fi
done

for path in /usr/local/bin/sensing_server /app/sensing_server /app/server /usr/local/bin/server; do
    if [ -x "$path" ]; then
        echo "[RuView] Starting: $path"
        exec "$path"
    fi
done

echo "[RuView] ERROR: Could not find server binary."
exit 1
