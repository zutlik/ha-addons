# Claude Code Add-on

Run Claude Code as a persistent AI agent on your Home Assistant device.

## First-time Setup

1. **Install the add-on** and set your configuration options (see below).
2. **Open the Web UI** (the "Open Web UI" button in the add-on page) — this opens an interactive terminal.
3. In the terminal, run:
   ```
   claude login
   ```
4. A browser tab will open asking you to sign in with your **Claude.ai account** (Pro or Max subscription required).
5. After successful login, **restart the add-on**.
6. Claude Code will start automatically on every future restart.

## Configuration Options

| Option | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | No | — | Bot token from [@BotFather](https://t.me/BotFather). Enables Telegram integration. |
| `WORK_DIR` | No | `/share/claude-workspace` | Directory where Claude Code runs and stores files. |
| `AUTO_UPDATE_CHECK` | No | `true` | Check for Claude Code updates on each startup. Only downloads if a newer version is available. |

## Telegram Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Paste the token into `TELEGRAM_BOT_TOKEN` in the add-on configuration.
3. Restart the add-on.
4. DM your bot — it will reply with a **pairing code**.
5. Approve the pairing in the terminal (Web UI): the pairing code will appear, type `yes` to approve.

After pairing, you can send prompts directly to Claude Code via Telegram.

## Remote Control

When Claude Code starts, it registers a remote control session at **claude.ai/code**.

The session URL is:
- Printed in the **add-on log** (visible in Supervisor → Claude Code → Log)
- Saved to `/data/remote_control_url.txt` (readable from the Web UI terminal)
- Shown as a **persistent notification** in your Home Assistant dashboard

You can open the URL in any browser or the Claude mobile app to control the session from anywhere.

## Memory & Continuity

Claude Code always starts with `--continue` to resume the last session.

A `CLAUDE.md` file is automatically created in your workspace with instructions to:
- Read `memory.md` at the start of each session
- Update `memory.md` with context, tasks, and preferences
- Maintain continuity across restarts

## Updates

When `AUTO_UPDATE_CHECK` is enabled, the add-on checks npm for a newer `@anthropic-ai/claude-code` version on each startup. If found, it downloads and installs it once — the binary is stored in persistent storage (`/data/npm-global`) and reused on subsequent restarts without re-downloading.

To force a manual update: disable `AUTO_UPDATE_CHECK`, restart (skips check), re-enable it, restart again.

## Web Terminal

The Web UI exposes a full bash terminal in your browser (port 7681, via ttyd). Use it to:
- Run `claude login` for first-time authentication
- Inspect files in the workspace
- Run `claude` commands directly
- Check `cat /data/remote_control_url.txt` for the latest session URL

## Credentials

OAuth credentials are stored in `/data/.claude/.credentials.json` and persist across container rebuilds. Tokens refresh automatically while the session is active.

To copy credentials from another machine (instead of doing `claude login` on the device):
```bash
# On your Mac/PC:
scp ~/.claude/.credentials.json root@homeassistant.local:/data/addon_data/local_claude-code/.claude/
```
