#!/bin/bash
# Attach to the running claude daemon's tmux session.
# Drop to the claude user (same UID as the daemon) so the tmux socket at
# /tmp/tmux-1000/default is accessible. Detach with Ctrl-b then d.
exec su -s /bin/bash claude -c '
    export HOME=/data/claude
    export NPM_GLOBAL=/data/claude/npm-global
    export PATH=$NPM_GLOBAL/bin:/root/.bun/bin:$PATH
    if ! tmux has-session -t claude 2>/dev/null; then
        echo "No claude tmux session. Is the daemon running? Check the add-on log." >&2
        exit 1
    fi
    echo "Attaching to claude session. Detach: Ctrl-b then d."
    exec tmux attach -t claude
'
