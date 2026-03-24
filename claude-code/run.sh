#!/bin/bash
# Claude Code Add-on entrypoint
#
# HA add-on containers have no CAP_CHOWN — chown always fails.
# Strategy: mkdir /data/claude as root with chmod 777, then run
# everything inside it as the non-root `claude` user so all files
# are created with the correct ownership from the start.

set -e

echo "[claude-code] Starting Claude Code Add-on..."

CLAUDE_HOME="/data/claude"

# ============================================================
# Bootstrap: create /data/claude and make it writable by the
# claude user. chmod is allowed (CAP_FOWNER); chown is not.
# ============================================================
mkdir -p "$CLAUDE_HOME"
chmod 777 "$CLAUDE_HOME"

# ============================================================
# Read options from HA supervisor (root-owned, read as root)
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
chmod 777 "$WORK_DIR" 2>/dev/null || true

# ============================================================
# All remaining setup runs as the claude user so every file
# created under /data/claude/ is claude-owned. No chown needed.
# ============================================================
su -s /bin/bash claude << SETUP_EOF
set -e
export HOME="$CLAUDE_HOME"
export NPM_GLOBAL="$CLAUDE_HOME/npm-global"
export PATH="\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH"

# Create subdirectory tree as claude user (correct ownership from birth)
mkdir -p "\$NPM_GLOBAL" \
         "$CLAUDE_HOME/.claude/channels/telegram" \
         "$CLAUDE_HOME/.npm"

npm config set prefix "\$NPM_GLOBAL" 2>/dev/null || true

# --- Smart update check ---
if [ "$AUTO_UPDATE" = "true" ]; then
    echo "[claude-code] Checking for Claude Code updates..."
    INSTALLED=\$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "none")
    LATEST=\$(npm show @anthropic-ai/claude-code version 2>/dev/null || echo "\$INSTALLED")
    if [ "\$INSTALLED" = "none" ] || [ "\$INSTALLED" != "\$LATEST" ]; then
        echo "[claude-code] Installing Claude Code \$LATEST (was: \$INSTALLED)..."
        npm install -g @anthropic-ai/claude-code@latest
        echo "[claude-code] Claude Code installed: \$(claude --version 2>/dev/null || echo 'unknown')"
    else
        echo "[claude-code] Claude Code \$INSTALLED is up to date."
    fi
fi

# --- Telegram token ---
if [ -n "$TELEGRAM_TOKEN" ]; then
    echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN" > "$CLAUDE_HOME/.claude/channels/telegram/.env"
fi

# --- CLAUDE.md ---
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
SETUP_EOF

# ============================================================
# Start ttyd web terminal (runs as root — fine for ttyd)
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
if [ ! -f "$CLAUDE_HOME/.claude/.credentials.json" ]; then
    echo "[claude-code] ============================================================"
    echo "[claude-code] NOT AUTHENTICATED"
    echo "[claude-code] Open the add-on Web UI and run: claude login"
    echo "[claude-code] After login, restart this add-on."
    echo "[claude-code] ============================================================"
    wait $TTYD_PID
    exit 0
fi

# ============================================================
# One-time Telegram plugin setup (re-runs only when token changes)
# ============================================================
TELEGRAM_MARKER="$CLAUDE_HOME/.claude/.telegram_plugin_configured"
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
        export NPM_GLOBAL=$CLAUDE_HOME/npm-global
        export PATH=\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
        cd '$WORK_DIR' && claude --dangerously-skip-permissions --no-color
    " 2>&1 | while IFS= read -r line; do echo "[telegram-setup] $line"; done

    echo "$TELEGRAM_TOKEN" > "$TELEGRAM_MARKER"
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
    export NPM_GLOBAL=$CLAUDE_HOME/npm-global
    export PATH=\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
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
