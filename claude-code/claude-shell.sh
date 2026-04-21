#!/bin/bash
# Invoked by ttyd — give the user an interactive shell as the claude user
# with the same HOME/PATH that run.sh uses, so `claude login` writes creds
# to /data/claude/.claude/ (the persistent path run.sh reads on boot).
exec su -s /bin/bash claude -c '
    export HOME=/data/claude
    export NPM_GLOBAL=/data/claude/npm-global
    export PATH=$NPM_GLOBAL/bin:/root/.bun/bin:$PATH
    cd "$HOME" 2>/dev/null || cd /
    if command -v tmux >/dev/null 2>&1 && tmux has-session -t claude 2>/dev/null; then
        echo "Claude daemon is running. Run \"claude-attach\" to attach (Ctrl-b d to detach)."
    fi
    exec bash
'
