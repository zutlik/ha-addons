#!/usr/bin/env bash
# RuView WiFi Presence — addon run script
# Lifecycle:
#   startup  → write HA sensor package + patch configuration.yaml → start server
#   shutdown → SIGTERM trap → remove what we added → stop server gracefully

SERVER_PID=""
MARKER="/data/ruview_config_marker"  # persists in /data (survives restarts, removed on cleanup)

# ── Cleanup — called on SIGTERM (stop, restart, or uninstall) ────────────────
cleanup() {
    echo "[RuView] Shutdown signal received — running cleanup..."

    # 1. Gracefully stop the server child process
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[RuView] Stopping server (PID $SERVER_PID)..."
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi

    # 2. Remove the sensor package we installed
    if [ -f /config/packages/ruview.yaml ]; then
        rm -f /config/packages/ruview.yaml
        echo "[RuView] Removed /config/packages/ruview.yaml"
        # Remove the directory if we left it empty
        rmdir /config/packages 2>/dev/null && echo "[RuView] Removed empty /config/packages/" || true
    fi

    # 3. Revert configuration.yaml based on what we actually changed
    revert_configuration_yaml

    echo "[RuView] Cleanup complete."
    echo "[RuView] Restart Home Assistant to deactivate the sensors."
    exit 0
}

revert_configuration_yaml() {
    local CONFIG="/config/configuration.yaml"

    [ -f "$MARKER" ] || { echo "[RuView] No config marker — configuration.yaml was not modified, skipping revert."; return 0; }

    local action
    action=$(cat "$MARKER")

    case "$action" in
        full_block_added)
            # We appended an entire homeassistant: block — remove it.
            # The block starts with the sentinel comment we wrote.
            if grep -q "^# Added by RuView addon" "$CONFIG" 2>/dev/null; then
                # Delete the blank line before the comment + comment + homeassistant: + packages: line (4 lines total)
                sed -i '/^# Added by RuView addon — loads \/config\/packages/{ N; N; N; d }' "$CONFIG"
                # Also remove any preceding blank line left behind
                sed -i -e '/^[[:space:]]*$/{N; /^\n# Added by RuView/d}' "$CONFIG" 2>/dev/null || true
                echo "[RuView] Removed homeassistant: packages block from configuration.yaml"
            else
                echo "[RuView] homeassistant block marker not found — configuration.yaml may have been edited manually, skipping."
            fi
            ;;

        packages_line_added)
            # We injected a single "  packages: !include_dir_named packages" line
            # under an existing homeassistant: block.
            sed -i '/^  packages: !include_dir_named packages$/d' "$CONFIG"
            echo "[RuView] Removed packages: line from configuration.yaml"
            ;;

        no_change)
            echo "[RuView] configuration.yaml was not modified by this addon — nothing to revert."
            ;;

        *)
            echo "[RuView] Unknown config marker '$action' — skipping revert."
            ;;
    esac

    rm -f "$MARKER"
}

# Register the cleanup trap for graceful shutdown / uninstall
trap cleanup TERM INT

# ── 1. Drop the HA sensors package ───────────────────────────────────────────
mkdir -p /config/packages
cp /tmp/ruview_ha_package.yaml /config/packages/ruview.yaml
echo "[RuView] Sensor package written to /config/packages/ruview.yaml"

# ── 2. Patch configuration.yaml to load /config/packages/ ────────────────────
# We record exactly what we did so cleanup can undo only our change.
CONFIG="/config/configuration.yaml"

if grep -q "packages:" "$CONFIG" 2>/dev/null; then
    echo "[RuView] Packages already enabled in configuration.yaml — skipping."
    echo "no_change" > "$MARKER"

elif grep -q "^homeassistant:" "$CONFIG" 2>/dev/null; then
    # homeassistant: block exists — inject the packages: line under it.
    sed -i '/^homeassistant:/a\  packages: !include_dir_named packages' "$CONFIG"
    echo "packages_line_added" > "$MARKER"
    echo "[RuView] Injected packages: line under existing homeassistant: block."

else
    # No homeassistant: block — append a fully-formed one with our sentinel comment.
    cat >> "$CONFIG" << 'EOF'

# Added by RuView addon — loads /config/packages/*.yaml on HA startup
homeassistant:
  packages: !include_dir_named packages
EOF
    echo "full_block_added" > "$MARKER"
    echo "[RuView] Appended homeassistant: packages block to configuration.yaml."
fi

echo "[RuView] Restart Home Assistant once to activate the sensors."

# ── 3. Read CSI_SOURCE from HA addon options (/data/options.json) ─────────────
OPTIONS="/data/options.json"
if [ -f "$OPTIONS" ]; then
    CSI_SOURCE=$(python3 -c "import json; print(json.load(open('$OPTIONS')).get('CSI_SOURCE','simulate'))" 2>/dev/null || echo "simulate")
    export CSI_SOURCE
    echo "[RuView] CSI_SOURCE=$CSI_SOURCE (from addon options)"
else
    export CSI_SOURCE="${CSI_SOURCE:-simulate}"
    echo "[RuView] CSI_SOURCE=$CSI_SOURCE (default)"
fi

# ── NOTE on Linux WiFi support ────────────────────────────────────────────────
# The upstream sensing-server binary only implements WiFi scanning via Windows'
# netsh command. On Linux/Pi the supported sources are:
#   simulate  → synthetic DensePose data (recommended, all HA sensors work)
#   esp32     → real CSI from an ESP32 module over UDP port 5005
#   wifi      → Windows-only (netsh), falls back to simulate on Linux
if [ "$CSI_SOURCE" = "wifi" ] && [ "$(uname -s)" = "Linux" ]; then
    echo "[RuView] WARNING: CSI_SOURCE=wifi is Windows-only (uses netsh)."
    echo "[RuView] On Linux/Pi, 'wifi' will fall back to simulated data."
    echo "[RuView] Use 'esp32' for real hardware sensing, or 'simulate' to suppress this warning."
fi

# ── 4. Start the server as a child process (not exec) so the trap fires ───────
start_server() {
    local bin="$1"
    echo "[RuView] Starting: $bin --source $CSI_SOURCE"
    env "CSI_SOURCE=$CSI_SOURCE" "$bin" --source "$CSI_SOURCE" &
    SERVER_PID=$!
    echo "[RuView] Server PID: $SERVER_PID"
    wait "$SERVER_PID"
    local exit_code=$?
    echo "[RuView] Server exited with code $exit_code"
    exit "$exit_code"
}

# Try PATH first
for bin in sensing-server sensing_server wifi-densepose server; do
    if command -v "$bin" &>/dev/null; then
        start_server "$bin"
    fi
done

# Try known absolute paths
for path in \
    /usr/local/bin/sensing-server \
    /usr/local/bin/sensing_server \
    /app/sensing-server \
    /app/sensing_server \
    /app/server \
    /usr/local/bin/server; do
    if [ -x "$path" ]; then
        start_server "$path"
    fi
done

# Last resort: scan filesystem
FOUND=$(find /usr/local/bin /app /opt -maxdepth 2 -type f -executable 2>/dev/null \
    | grep -E 'sensing|densepose|server|wifi' | head -1)
if [ -n "$FOUND" ]; then
    start_server "$FOUND"
fi

echo "[RuView] ERROR: Could not find server binary."
exit 1
