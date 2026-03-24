#!/bin/bash
# Claude Code Add-on entrypoint
#
# /data is owned by HA Supervisor (root) — we never chown it.
# All claude-owned state lives under /data/claude/ which we create
# with the right ownership before switching to the non-root `claude` user.

set -e

echo "[claude-code] Starting Claude Code Add-on..."

# ============================================================
# Paths
# /data/options.json  — written by HA Supervisor (root-owned, read-only for us)
# /data/claude/       — our persistent state, owned by the claude user
# ============================================================
CLAUDE_HOME="/data/claude"
NPM_GLOBAL="$CLAUDE_HOME/npm-global"
CREDENTIALS="$CLAUDE_HOME/.claude/.credentials.json"
TELEGRAM_MARKER="$CLAUDE_HOME/.claude/.telegram_plugin_configured"

# Create our subdirectory tree and hand it to the claude user
mkdir -p \
    "$NPM_GLOBAL" \
    "$CLAUDE_HOME/.claude/channels/telegram" \
    "$CLAUDE_HOME/.npm"
chown -R claude:claude "$CLAUDE_HOME"

# npm global prefix (runs as root for the update check, still writes to claude-owned dir)
export HOME="$CLAUDE_HOME"
export NPM_GLOBAL
export PATH="$NPM_GLOBAL/bin:/root/.bun/bin:$PATH"
npm config set prefix "$NPM_GLOBAL" 2>/dev/null || true

# ============================================================
# Read options from HA supervisor (/data/options.json is root-owned)
# ============================================================
OPTIONS="/data/options.json"

get_option() {
    local key="$1" default="$2"
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
chown claude:claude "$WORK_DIR" 2>/dev/null || true

# ============================================================
# Smart update check (runs as root — npm is fine as root)
# ============================================================
if [ "$AUTO_UPDATE" = "true" ]; then
    echo "[claude-code] Checking for Claude Code updates..."
    INSTALLED=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "none")
    LATEST=$(npm show @anthropic-ai/claude-code version 2>/dev/null || echo "$INSTALLED")

    if [ "$INSTALLED" = "none" ] || [ "$INSTALLED" != "$LATEST" ]; then
        echo "[claude-code] Installing Claude Code $LATEST (was: $INSTALLED)..."
        npm install -g @anthropic-ai/claude-code@latest
        chown -R claude:claude "$NPM_GLOBAL"
        echo "[claude-code] Claude Code installed: $(claude --version 2>/dev/null || echo 'unknown')"
    else
        echo "[claude-code] Claude Code $INSTALLED is up to date."
    fi
fi

# ============================================================
# Write Telegram token to .env (keep in sync with config)
# ============================================================
if [ -n "$TELEGRAM_TOKEN" ]; then
    echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN" > "$CLAUDE_HOME/.claude/channels/telegram/.env"
    chown claude:claude "$CLAUDE_HOME/.claude/channels/telegram/.env"
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
    chown claude:claude "$WORK_DIR/CLAUDE.md" 2>/dev/null || true
    echo "[claude-code] Created CLAUDE.md in $WORK_DIR"
fi

# ============================================================
# Start ttyd web terminal (always on)
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
# Check authentication
# ============================================================
if [ ! -f "$CREDENTIALS" ]; then
    echo "[claude-code] ============================================================"
    echo "[claude-code] NOT AUTHENTICATED"
    echo "[claude-code] Open the add-on Web UI and run: claude login"
    echo "[claude-code] After login, restart this add-on."
    echo "[claude-code] ============================================================"
    wait $TTYD_PID
    exit 0
fi

# ============================================================
# One-time Telegram plugin setup
# Re-runs only when the token changes.
# ============================================================
CONFIGURED_TOKEN=""
[ -f "$TELEGRAM_MARKER" ] && CONFIGURED_TOKEN=$(cat "$TELEGRAM_MARKER")

if [ -n "$TELEGRAM_TOKEN" ] && [ "$CONFIGURED_TOKEN" != "$TELEGRAM_TOKEN" ]; then
    echo "[claude-code] Running one-time Telegram plugin setup..."
    {
        echo "/plugin marketplace add anthropics/claude-plugins-official"
        echo "/plugin install telegram@claude-plugins-official"
        echo "/telegram:configure $TELEGRAM_TOKEN"
        echo "/exit"
    } | timeout 180 su -s /bin/bash claude -c "
        export HOME=$CLAUDE_HOME
        export NPM_GLOBAL=$NPM_GLOBAL
        export PATH=$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
        cd '$WORK_DIR' && claude --dangerously-skip-permissions --no-color
    " 2>&1 | while IFS= read -r line; do echo "[telegram-setup] $line"; done

    echo "$TELEGRAM_TOKEN" > "$TELEGRAM_MARKER"
    chown claude:claude "$TELEGRAM_MARKER"
    echo "[claude-code] Telegram plugin setup complete."
fi

# ============================================================
# Start Claude Code daemon as non-root claude user
# ============================================================
CHANNELS_ARG=""
if [ -n "$TELEGRAM_TOKEN" ]; then
    CHANNELS_ARG="--channels plugin:telegram@claude-plugins-official"
    echo "[claude-code] Starting with Telegram channel enabled."
fi

echo "[claude-code] Starting Claude Code in $WORK_DIR ..."
echo "[claude-code] Remote control URL will appear in the logs and as an HA notification."

su -s /bin/bash claude -c "
    export HOME=$CLAUDE_HOME
    export NPM_GLOBAL=$NPM_GLOBAL
    export PATH=$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
    cd '$WORK_DIR' && claude \
        --continue \
        --dangerously-skip-permissions \
        --remote-control \
        $CHANNELS_ARG
" 2>&1 | while IFS= read -r line; do
    echo "[claude] $line"

    if echo "$line" | grep -qE 'https://[a-zA-Z0-9./_-]+/rc/[a-zA-Z0-9_-]+'; then
        URL=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9./_-]+/rc/[a-zA-Z0-9_-]+' | head -1)
        echo "$URL" > "$CLAUDE_HOME/remote_control_url.txt"

        echo "[claude-code] ========================================================"
        echo "[claude-code] REMOTE CONTROL URL: $URL"
        echo "[claude-code] ========================================================"

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
