#!/bin/bash
# Claude Code Add-on entrypoint
#
# Requires full_access: true (set in config.yaml) so that the container
# has CAP_SETUID + CAP_SETGID, allowing `su claude` to drop root privileges
# before invoking claude. (--dangerously-skip-permissions refuses to run
# as root.)

set -e

echo "[claude-code] Starting Claude Code Add-on..."

CLAUDE_HOME="/data/claude"

# ============================================================
# Bootstrap: create /data/claude writable by the claude user.
# CAP_CHOWN is not available, so we use chmod 777 instead.
# ============================================================
mkdir -p "$CLAUDE_HOME"
chmod 777 "$CLAUDE_HOME"
# Legacy boots created subtrees as root; without CAP_CHOWN we can't chown,
# so make everything under /data/claude writable by the claude user.
chmod -R a+rwX "$CLAUDE_HOME" 2>/dev/null || true

# ============================================================
# Read options (root-owned /data/options.json, read as root)
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
TELEGRAM_CHAT_ID=$(get_option "TELEGRAM_CHAT_ID" "")
WORK_DIR=$(get_option "WORK_DIR" "/share/claude-workspace")
AUTO_UPDATE=$(get_option "AUTO_UPDATE_CHECK" "true")

mkdir -p "$WORK_DIR"
chmod 777 "$WORK_DIR" 2>/dev/null || true

# ============================================================
# Pre-accept the workspace trust dialog. Without this, claude shows
# "Is this a project you trust?" on startup and our headless daemon
# has no one to press 1. We write ~/.claude.json (HOME=/data/claude)
# with the flags claude sets when you answer 1 interactively, merging
# with any existing config (jq deep-merge).
# ============================================================
CLAUDE_JSON="$CLAUDE_HOME/.claude.json"
[ ! -f "$CLAUDE_JSON" ] && echo '{}' > "$CLAUDE_JSON"
chmod 666 "$CLAUDE_JSON" 2>/dev/null || true
TRUST_PATCH=$(cat <<JSON
{
  "hasTrustDialogAccepted": true,
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true,
  "projects": {
    "$WORK_DIR": {
      "hasTrustDialogAccepted": true,
      "hasCompletedProjectOnboarding": true,
      "allowedTools": []
    }
  }
}
JSON
)
if MERGED=$(jq --argjson patch "$TRUST_PATCH" '. * $patch' "$CLAUDE_JSON" 2>/dev/null); then
    echo "$MERGED" > "$CLAUDE_JSON"
    echo "[claude-code] Pre-accepted workspace trust for $WORK_DIR."
else
    echo "$TRUST_PATCH" > "$CLAUDE_JSON"
    echo "[claude-code] Wrote fresh .claude.json (existing was malformed)."
fi
chmod 666 "$CLAUDE_JSON" 2>/dev/null || true

# ============================================================
# Write CLAUDE.md as root, BEFORE the su block.
# (Kept separate so backticks in the content are never inside an
# outer unquoted heredoc where the shell would try to execute them.)
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
# Run setup as the claude user so all files under /data/claude/
# are created with claude ownership (no chown needed).
# ============================================================
su -s /bin/bash claude -c "
    set -e
    export HOME=$CLAUDE_HOME
    export NPM_GLOBAL=$CLAUDE_HOME/npm-global
    export PATH=\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH

    mkdir -p \$NPM_GLOBAL \
             $CLAUDE_HOME/.claude/channels/telegram \
             $CLAUDE_HOME/.npm

    npm config set prefix \$NPM_GLOBAL 2>/dev/null || true

    if ! command -v claude >/dev/null 2>&1; then
        echo '[claude-code] Claude Code not installed yet, installing...'
        npm install -g @anthropic-ai/claude-code@latest
        echo \"[claude-code] Installed: \$(claude --version 2>/dev/null || echo unknown)\"
    elif [ '$AUTO_UPDATE' = 'true' ]; then
        echo '[claude-code] Checking for Claude Code updates...'
        INSTALLED=\$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
        LATEST=\$(npm show @anthropic-ai/claude-code version 2>/dev/null || true)
        if [ -z \"\$LATEST\" ]; then
            echo \"[claude-code] npm show failed (network?); keeping installed \$INSTALLED.\"
        elif [ \"\$INSTALLED\" != \"\$LATEST\" ]; then
            echo \"[claude-code] Updating Claude Code \$INSTALLED -> \$LATEST...\"
            npm install -g @anthropic-ai/claude-code@latest
            echo \"[claude-code] Installed: \$(claude --version 2>/dev/null || echo unknown)\"
        else
            echo \"[claude-code] Claude Code \$INSTALLED is up to date.\"
        fi
    fi

    if [ -n '$TELEGRAM_TOKEN' ]; then
        echo 'TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN' > $CLAUDE_HOME/.claude/channels/telegram/.env
    fi
"

# ============================================================
# Start ttyd web terminal
# ============================================================
INGRESS_ENTRY="${INGRESS_PATH:-}"
ttyd \
    --writable \
    --port 7681 \
    --interface 0.0.0.0 \
    ${INGRESS_ENTRY:+--base-path "${INGRESS_ENTRY}"} \
    /usr/local/bin/claude-shell &
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
# Telegram plugin setup. Marker includes a SETUP_VERSION so bumping it
# forces a re-run across upgrades (earlier versions silently marked
# setup "complete" even when it failed, so we need a way to re-run).
#
# The setup command is wrapped in `script` to give claude a PTY —
# without it, claude drops into --print mode and never processes our
# piped slash commands.
# ============================================================
SETUP_VERSION=2
TELEGRAM_MARKER="$CLAUDE_HOME/.claude/.telegram_plugin_configured"
CONFIGURED=""
[ -f "$TELEGRAM_MARKER" ] && CONFIGURED=$(cat "$TELEGRAM_MARKER")
EXPECTED="${SETUP_VERSION}:${TELEGRAM_TOKEN}"

if [ -n "$TELEGRAM_TOKEN" ] && [ "$CONFIGURED" != "$EXPECTED" ]; then
    echo "[claude-code] Running Telegram plugin setup (version $SETUP_VERSION)..."

    SETUP_INPUT=$(mktemp)
    chmod 644 "$SETUP_INPUT"
    {
        # Accept the "Bypass Permissions mode" warning (option 2 = Yes, I accept).
        # Claude should persist this to .claude.json after the first accept.
        echo "2"
        echo "/plugin marketplace add anthropics/claude-plugins-official"
        echo "/plugin install telegram@claude-plugins-official"
        echo "/telegram:configure $TELEGRAM_TOKEN"
        echo "/exit"
    } > "$SETUP_INPUT"

    timeout 180 su -s /bin/bash claude -c "
        export HOME=$CLAUDE_HOME
        export NPM_GLOBAL=$CLAUDE_HOME/npm-global
        export PATH=\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
        export NO_COLOR=1
        cd '$WORK_DIR' && exec script -qefc 'claude --dangerously-skip-permissions' /dev/null < '$SETUP_INPUT'
    " 2>&1 | while IFS= read -r line; do echo "[telegram-setup] $line"; done

    SETUP_EXIT=${PIPESTATUS[0]}
    rm -f "$SETUP_INPUT"

    if [ "$SETUP_EXIT" -eq 0 ]; then
        echo "$EXPECTED" > "$TELEGRAM_MARKER"
        echo "[claude-code] Telegram plugin setup complete."
    else
        echo "[claude-code] Telegram plugin setup FAILED (exit $SETUP_EXIT). Will retry on next boot."
        rm -f "$TELEGRAM_MARKER"
    fi

    # Debug: log what claude persisted to .claude.json after setup, so we can
    # see the exact key name used for bypass-permissions acceptance.
    if command -v jq >/dev/null; then
        echo "[claude-code] Top-level keys in .claude.json after setup:"
        jq -r 'keys[]' "$CLAUDE_JSON" 2>/dev/null | sed 's/^/[claude-code]   /'
    fi
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

# Restart loop: if claude exits (crash, stale session, SIGHUP), wait a bit and
# restart. Prevents the whole container from bouncing on every claude crash.
#
# --continue strategy: prefer resuming the latest conversation. If claude exits
# in under 15s while --continue is active, assume the session is corrupted
# (e.g. stale deferred-tool marker from an unclean shutdown) and drop to
# fresh-session mode for the rest of this boot.
TRY_CONTINUE=yes
while true; do
    CONTINUE_FLAG=""
    [ "$TRY_CONTINUE" = "yes" ] && CONTINUE_FLAG="--continue"
    [ -n "$CONTINUE_FLAG" ] \
        && echo "[claude-code] Launching claude (with --continue)..." \
        || echo "[claude-code] Launching claude (fresh session)..."

    START_TS=$(date +%s)

    # Wrap claude in `script` to allocate a pseudo-TTY. Without a TTY, claude
    # switches to --print mode and exits because no prompt was given. The PTY
    # keeps it in interactive mode so --channels and --remote-control work as
    # a long-running daemon. `script -q` silences the start/end banner,
    # `-e` propagates claude's exit code, `-f` flushes so our log is live.
su -s /bin/bash claude -c "
    export HOME=$CLAUDE_HOME
    export NPM_GLOBAL=$CLAUDE_HOME/npm-global
    export PATH=\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
    export NO_COLOR=1
    cd '$WORK_DIR' && exec script -qefc \"claude $CONTINUE_FLAG --dangerously-skip-permissions --remote-control $CHANNELS_ARG\" /dev/null
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

        # DM the URL to Telegram if both bot token and chat ID are configured.
        if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
            curl -sf -X POST \
                "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
                --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
                --data-urlencode "text=Claude Code is ready. Remote control: ${URL}" \
                --data-urlencode "disable_web_page_preview=true" \
                > /dev/null \
                && echo "[claude-code] Posted remote control URL to Telegram chat ${TELEGRAM_CHAT_ID}." \
                || echo "[claude-code] Failed to post remote control URL to Telegram (check bot token / chat id)."
        fi
    fi
done

    DURATION=$(( $(date +%s) - START_TS ))
    if [ "$TRY_CONTINUE" = "yes" ] && [ "$DURATION" -lt 15 ]; then
        echo "[claude-code] --continue exited in ${DURATION}s — session likely corrupted. Subsequent restarts this boot will start fresh."
        TRY_CONTINUE=no
    else
        echo "[claude-code] Claude exited after ${DURATION}s. Restarting in 10s..."
    fi
    sleep 10
done
