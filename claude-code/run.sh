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
DAEMON_AUTOSTART=$(get_option "DAEMON_AUTOSTART" "true")

mkdir -p "$WORK_DIR"
chmod 777 "$WORK_DIR" 2>/dev/null || true

# ============================================================
# Telegram config diagnostics + startup ping. Fires independently of URL
# extraction so we know whether the Telegram pipe works at all.
# ============================================================
tg_send() {
    local text="$1"
    local resp
    resp=$(curl -sS -X POST \
        "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${text}" \
        --data-urlencode "disable_web_page_preview=true" 2>&1)
    if echo "$resp" | grep -q '"ok":true'; then
        echo "[claude-code] Telegram OK: sent '${text:0:60}...'"
        return 0
    else
        echo "[claude-code] Telegram FAIL: $resp"
        return 1
    fi
}

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "[claude-code] Telegram: TELEGRAM_BOT_TOKEN is empty — startup DM disabled."
elif [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "[claude-code] Telegram: TELEGRAM_CHAT_ID is empty — startup DM disabled (get your chat id from @userinfobot)."
else
    echo "[claude-code] Telegram: token+chat_id present, sending startup ping to chat ${TELEGRAM_CHAT_ID}..."
    tg_send "Claude Code add-on starting up..." || true
fi

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
# DAEMON_AUTOSTART=false → manual-setup mode: skip Telegram setup AND
# the claude daemon launch, keep only ttyd running. Use this to open
# the Web UI and manually run `claude --dangerously-skip-permissions`
# to accept one-time TUI prompts (trust dialog, bypass-permissions
# warning). After prompts are accepted and claude has persisted them,
# flip DAEMON_AUTOSTART back to true.
# ============================================================
if [ "$DAEMON_AUTOSTART" != "true" ]; then
    echo "[claude-code] ============================================================"
    echo "[claude-code] DAEMON_AUTOSTART=false — not launching the claude daemon."
    echo "[claude-code] Open the Web UI and run:"
    echo "[claude-code]     claude --dangerously-skip-permissions"
    echo "[claude-code] Accept any TUI prompts (down-arrow + Enter for option 2)."
    echo "[claude-code] Then /exit, flip DAEMON_AUTOSTART to true, restart the add-on."
    echo "[claude-code] ============================================================"
    wait $TTYD_PID
    exit 0
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
# The claude daemon runs inside a tmux session so you can attach to it from
# the Web UI (run `claude-attach`) and interact with its TUI directly —
# accept prompts, type messages, watch it work — then detach with Ctrl-b d.
# tmux also provides the PTY that claude needs to stay in interactive mode.
TMUX_SESSION=claude

TRY_CONTINUE=yes
while true; do
    CONTINUE_FLAG=""
    [ "$TRY_CONTINUE" = "yes" ] && CONTINUE_FLAG="--continue"
    [ -n "$CONTINUE_FLAG" ] \
        && echo "[claude-code] Launching claude (with --continue)..." \
        || echo "[claude-code] Launching claude (fresh session)..."

    START_TS=$(date +%s)

    # Start the daemon inside a detached tmux session.
    su -s /bin/bash claude -c "
        export HOME=$CLAUDE_HOME
        export NPM_GLOBAL=$CLAUDE_HOME/npm-global
        export PATH=\$NPM_GLOBAL/bin:/root/.bun/bin:\$PATH
        export NO_COLOR=1
        tmux kill-session -t $TMUX_SESSION 2>/dev/null || true
        cd '$WORK_DIR' && tmux new-session -d -s $TMUX_SESSION -x 200 -y 50 \
            \"claude --model claude-sonnet-4-6 $CONTINUE_FLAG --dangerously-skip-permissions --remote-control $CHANNELS_ARG\"
    "

    echo "[claude-code] Daemon running in tmux session '$TMUX_SESSION'. Run 'claude-attach' from the Web UI to view."

    # Background URL watcher: polls `tmux capture-pane -p`, which renders the
    # pane to plain text (no ANSI, no cursor codes) so grep matches reliably.
    # If the URL doesn't land after N polls, dump a pane snapshot to the log
    # so we can see what's actually there vs. what our regex expects.
    (
        URL_POSTED=""
        POLL=0
        DIAG_DUMPED=""
        while true; do
            sleep 3
            POLL=$((POLL + 1))
            su -s /bin/bash claude -c "tmux has-session -t $TMUX_SESSION 2>/dev/null" || break
            [ -n "$URL_POSTED" ] && continue
            SNAPSHOT=$(su -s /bin/bash claude -c "tmux capture-pane -t $TMUX_SESSION -p -S -5000" 2>&1)
            CAP_EXIT=$?
            if [ "$CAP_EXIT" -ne 0 ]; then
                echo "[claude-code] capture-pane failed (exit $CAP_EXIT): $SNAPSHOT"
                continue
            fi
            URL=$(echo "$SNAPSHOT" | grep -oE 'https://[a-zA-Z0-9./_-]+/rc/[a-zA-Z0-9_-]+' | head -1)
            if [ -z "$URL" ]; then
                # After ~15s with no URL, dump what we DO see so we can tune the
                # regex / confirm the daemon actually rendered the URL.
                if [ -z "$DIAG_DUMPED" ] && [ "$POLL" -ge 5 ]; then
                    DIAG_DUMPED=yes
                    echo "[claude-code] --- URL not found after ${POLL} polls; pane snapshot follows ---"
                    echo "$SNAPSHOT" | tail -n 60 | sed 's/^/[pane] /'
                    echo "[claude-code] --- end pane snapshot (will keep polling) ---"
                fi
                continue
            fi

            URL_POSTED=yes
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

            if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
                tg_send "Claude Code is ready. Remote control: ${URL}" || true
            fi
        done
    ) &
    WATCHER_PID=$!

    # Block until the tmux session dies (claude exited, or user ran
    # `tmux kill-session`). Poll every 2s so restarts remain responsive.
    while su -s /bin/bash claude -c "tmux has-session -t $TMUX_SESSION 2>/dev/null"; do
        sleep 2
    done

    kill "$WATCHER_PID" 2>/dev/null || true
    wait "$WATCHER_PID" 2>/dev/null || true

    DURATION=$(( $(date +%s) - START_TS ))
    if [ "$TRY_CONTINUE" = "yes" ] && [ "$DURATION" -lt 15 ]; then
        echo "[claude-code] --continue exited in ${DURATION}s — session likely corrupted. Subsequent restarts this boot will start fresh."
        TRY_CONTINUE=no
    else
        echo "[claude-code] Claude exited after ${DURATION}s. Restarting in 10s..."
    fi
    sleep 10
done
