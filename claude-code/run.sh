#!/bin/bash
# Claude Code Add-on entrypoint
# Manages: update check, Telegram plugin setup, CLAUDE.md, ttyd terminal, Claude daemon

set -e

echo "[claude-code] Starting Claude Code Add-on..."

# ============================================================
# Persistent paths: /data survives container rebuilds in HA
# ============================================================
export HOME="/data"
export NPM_GLOBAL="/data/npm-global"
export PATH="$NPM_GLOBAL/bin:/root/.bun/bin:$PATH"

mkdir -p "$NPM_GLOBAL" /data/.claude/channels/telegram
npm config set prefix "$NPM_GLOBAL" 2>/dev/null || true

# ============================================================
# Read options from HA supervisor
# ============================================================
OPTIONS="/data/options.json"

get_option() {
    local key="$1"
    local default="$2"
    if [ -f "$OPTIONS" ]; then
        val=$(jq -r ".$key // empty" "$OPTIONS" 2>/dev/null)
        echo "${val:-$default}"
    else
        echo "$default"
    fi
}

TELEGRAM_TOKEN=$(get_option "TELEGRAM_BOT_TOKEN" "")
WORK_DIR=$(get_option "WORK_DIR" "/share/claude-workspace")
AUTO_UPDATE=$(get_option "AUTO_UPDATE_CHECK" "true")

mkdir -p "$WORK_DIR"

# ============================================================
# Smart update check: only download when a newer version exists
# ============================================================
if [ "$AUTO_UPDATE" = "true" ]; then
    echo "[claude-code] Checking for Claude Code updates..."
    INSTALLED=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "none")
    LATEST=$(npm show @anthropic-ai/claude-code version 2>/dev/null || echo "$INSTALLED")

    if [ "$INSTALLED" = "none" ] || [ "$INSTALLED" != "$LATEST" ]; then
        echo "[claude-code] Installing Claude Code $LATEST (was: $INSTALLED)..."
        npm install -g @anthropic-ai/claude-code@latest
        echo "[claude-code] Claude Code installed: $(claude --version 2>/dev/null || echo 'unknown')"
    else
        echo "[claude-code] Claude Code $INSTALLED is up to date."
    fi
fi

# ============================================================
# Write Telegram token to .env (always keep in sync with config)
# ============================================================
if [ -n "$TELEGRAM_TOKEN" ]; then
    mkdir -p /data/.claude/channels/telegram
    echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN" > /data/.claude/channels/telegram/.env
fi

# ============================================================
# Create CLAUDE.md in workspace if it doesn't exist yet
# ============================================================
if [ ! -f "$WORK_DIR/CLAUDE.md" ]; then
    cat > "$WORK_DIR/CLAUDE.md" << 'CLAUDEMD'
# Claude Code - Persistent Agent Instructions

You are running as a persistent agent on a Raspberry Pi running Home Assistant OS.

## Memory Protocol

At the start of EVERY session:
1. Check if `memory.md` exists in this directory.
2. If it does, read it and briefly summarize the key context to yourself before responding.
3. Mention any relevant remembered context proactively when it's useful.

At the end of any meaningful session, or when asked, update `memory.md` with:
- Summary of what was accomplished
- Ongoing tasks or open requests
- User preferences and working style learned
- Important paths, credentials, or system details discovered
- Date of last update

Keep `memory.md` concise (aim for under 200 lines). Prioritize actionable context over verbose history.

## Environment

- Platform: Raspberry Pi, Home Assistant OS
- Workspace: this directory (/share/claude-workspace)
- Home Assistant is running locally; you can interact with it via the HA API
- /share is mounted read-write

## Behavior Guidelines

- Be proactive: if you notice something that needs fixing or could be improved, mention it
- You have broad permissions - use them responsibly
- When writing automations or scripts for HA, test them before declaring success
CLAUDEMD
    echo "[claude-code] Created CLAUDE.md in $WORK_DIR"
fi

# ============================================================
# Start ttyd web terminal (always on - used for login + interactive access)
# HA ingress injects INGRESS_PATH (e.g. /api/hassio_ingress/<token>)
# ttyd must be told this base-path so assets and WS connect correctly.
# ============================================================
INGRESS_ENTRY="${INGRESS_PATH:-}"
ttyd \
    --writable \
    --port 7681 \
    --interface 0.0.0.0 \
    ${INGRESS_ENTRY:+--base-path "${INGRESS_ENTRY}"} \
    bash &
TTYD_PID=$!
echo "[claude-code] Web terminal started (pid=$TTYD_PID) on port 7681 (ingress: ${INGRESS_ENTRY:-none})"

# ============================================================
# Check authentication - credentials live at /data/.claude/.credentials.json
# ============================================================
if [ ! -f "/data/.claude/.credentials.json" ]; then
    echo "[claude-code] ============================================================"
    echo "[claude-code] NOT AUTHENTICATED"
    echo "[claude-code] Open the add-on Web UI and run: claude login"
    echo "[claude-code] After login, restart this add-on."
    echo "[claude-code] ============================================================"
    # Keep ttyd running so the user can authenticate
    wait $TTYD_PID
    exit 0
fi

# ============================================================
# One-time Telegram plugin setup (runs automatically after first login)
#
# Marker file tracks whether setup was done for the current token.
# If the token changes in config, the marker is stale → re-run setup.
# ============================================================
TELEGRAM_MARKER="/data/.claude/.telegram_plugin_configured"
CONFIGURED_TOKEN=""
[ -f "$TELEGRAM_MARKER" ] && CONFIGURED_TOKEN=$(cat "$TELEGRAM_MARKER")

if [ -n "$TELEGRAM_TOKEN" ] && [ "$CONFIGURED_TOKEN" != "$TELEGRAM_TOKEN" ]; then
    echo "[claude-code] Running one-time Telegram plugin setup..."

    # Pipe the four setup commands into a headless Claude session.
    # /exit ensures Claude quits after executing them.
    # We use --no-color to keep the log readable.
    # timeout 180s guards against any command hanging indefinitely.
    {
        echo "/plugin marketplace add anthropics/claude-plugins-official"
        echo "/plugin install telegram@claude-plugins-official"
        echo "/telegram:configure $TELEGRAM_TOKEN"
        echo "/exit"
    } | timeout 180 claude \
            --dangerously-skip-permissions \
            --no-color \
            --cwd "$WORK_DIR" 2>&1 \
        | while IFS= read -r line; do echo "[telegram-setup] $line"; done

    # Persist the token hash so we don't re-run setup on the next restart
    echo "$TELEGRAM_TOKEN" > "$TELEGRAM_MARKER"
    echo "[claude-code] Telegram plugin setup complete."
fi

# ============================================================
# Start Claude Code daemon
# --continue:                   resume last session (preserves conversation history)
# --dangerously-skip-permissions: needed for headless/unattended operation
# --remote-control:             register a session URL at claude.ai/code
# --channels:                   Telegram integration (only if token is configured)
# ============================================================
CHANNELS_ARG=""
if [ -n "$TELEGRAM_TOKEN" ]; then
    CHANNELS_ARG="--channels plugin:telegram@claude-plugins-official"
    echo "[claude-code] Starting with Telegram channel enabled."
fi

echo "[claude-code] Starting Claude Code in $WORK_DIR ..."
echo "[claude-code] Remote control session URL will appear in the logs below."
echo "[claude-code] It is also saved to /data/remote_control_url.txt and shown as an HA notification."

# Pipe claude output through a URL extractor:
#   - every line is forwarded to the HA supervisor log
#   - the remote-control session URL is saved to /data/remote_control_url.txt
#   - an HA persistent notification with a clickable link is created/updated
claude \
    --continue \
    --dangerously-skip-permissions \
    --remote-control \
    $CHANNELS_ARG \
    --cwd "$WORK_DIR" 2>&1 | \
while IFS= read -r line; do
    echo "[claude] $line"

    # Claude prints the remote-control URL on startup, e.g.:
    # https://app.claude.com/rc/<session-id>
    if echo "$line" | grep -qE 'https://[a-zA-Z0-9./_-]+/rc/[a-zA-Z0-9_-]+'; then
        URL=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9./_-]+/rc/[a-zA-Z0-9_-]+' | head -1)
        echo "$URL" > /data/remote_control_url.txt

        echo "[claude-code] ========================================================"
        echo "[claude-code] REMOTE CONTROL URL: $URL"
        echo "[claude-code] ========================================================"

        # Create/update a persistent HA dashboard notification with a clickable link
        curl -sf -X POST \
            -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
            -H "Content-Type: application/json" \
            "http://supervisor/core/api/services/persistent_notification/create" \
            -d "{
                \"title\": \"Claude Code - Remote Control\",
                \"message\": \"Session is ready.\\n\\n[Open remote control]($URL)\\n\\nOr copy the URL:\\n\`$URL\`\",
                \"notification_id\": \"claude_code_rc_url\"
            }" > /dev/null || true
    fi
done
