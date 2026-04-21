#!/bin/bash
# Attach to the running claude daemon's tmux session. Detach with Ctrl-b d.
#
# The Web UI shell is already running as the claude user (see claude-shell.sh),
# so we can attach directly. If invoked as anyone else, re-exec via sudo —
# the claude user has NOPASSWD sudo configured in the Dockerfile.
if [ "$(id -un)" != "claude" ]; then
    exec sudo -u claude -H /usr/local/bin/claude-attach "$@"
fi

export HOME=/data/claude
export NPM_GLOBAL=/data/claude/npm-global
export PATH=$NPM_GLOBAL/bin:/root/.bun/bin:$PATH

if ! tmux has-session -t claude 2>/dev/null; then
    echo "No claude tmux session. Is the daemon running? Check the add-on log." >&2
    exit 1
fi

echo "Attaching to claude session. Detach: Ctrl-b then d."
exec tmux attach -t claude
