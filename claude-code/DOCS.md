# Claude Code Add-on

Run Claude Code as a persistent AI agent on your Home Assistant device.

---

## First-time Setup

### Step 1 — Configure the add-on

Before starting, fill in the add-on configuration:

| Option | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | No | — | Bot token from [@BotFather](https://t.me/BotFather). Enables Telegram channel startup and direct startup DMs. |
| `TELEGRAM_CHAT_ID` | No | — | Your numeric Telegram user/chat ID. When set, the add-on sends startup DMs and pre-allowlists that ID for Telegram input. |
| `WORK_DIR` | No | `/share/claude-workspace` | Directory where Claude Code runs and stores files. |
| `AUTO_UPDATE_CHECK` | No | `true` | Check for Claude Code updates on each startup. Only downloads if a newer version is available. |
| `DAEMON_AUTOSTART` | No | `true` | Set false to keep only the Web UI terminal running for manual setup or debugging. |
| `HA_TOKEN` | No | — | Long-Lived Access Token fallback for Home Assistant API access if the supervisor token is unavailable. |

If you want Telegram, create a bot with [@BotFather](https://t.me/BotFather) now and copy the token into `TELEGRAM_BOT_TOKEN`. For the smoothest first boot, also set `TELEGRAM_CHAT_ID` to your numeric Telegram user ID from [@userinfobot](https://t.me/userinfobot).

### Step 2 — Authenticate with your Claude.ai account

1. Start the add-on.
2. Click **Open Web UI** — a terminal opens in your browser.
3. In the terminal, run:
   ```
   claude login
   ```
4. A browser tab opens — sign in with your **Claude.ai account** (Pro or Max subscription required).
5. After the login succeeds, the terminal will confirm authentication.

### Step 3 — Restart the add-on

Go back to the add-on page and click **Restart**.

On this restart, the add-on will automatically:
1. Detect that you are now authenticated.
2. Ensure the Home Assistant MCP server is registered for Claude Code.
3. If `TELEGRAM_BOT_TOKEN` is set:
   - Write the bot token to `/data/claude/.claude/channels/telegram/.env`
   - Enable `telegram@claude-plugins-official` in Claude Code user settings
   - If `TELEGRAM_CHAT_ID` is set, write it to the Telegram allowlist
   - Start Claude Code with `--channels plugin:telegram@claude-plugins-official`

> **That's it.** Claude Code is now running. You do not need to touch the terminal again unless something goes wrong.

---

## Telegram — Pairing your account

After the restart, Claude Code starts polling Telegram for messages.

If `TELEGRAM_CHAT_ID` is set, the add-on pre-allowlists that ID and your DM should reach Claude directly.

If `TELEGRAM_CHAT_ID` is not set, use the plugin's pairing flow:

1. Open Telegram and DM your bot (e.g. `/start`).
2. The bot replies with a **pairing code**.
3. Open the **Web UI terminal**, run `claude-attach`, then type these in Claude Code:
   ```
   /telegram:access pair <code>
   /telegram:access policy allowlist
   ```

After pairing, you can send prompts to Claude Code directly from Telegram and receive responses.

> The pairing is stored persistently and survives restarts. You only need to do this once.

---

## Remote Control

When Claude Code starts, it registers a remote control session reachable from anywhere via **claude.ai/code**.

The session URL is automatically:
- Printed in the **add-on log** (Supervisor → Claude Code → Log)
- Saved to `/data/claude/remote_control_url.txt` (readable from the Web UI terminal: `cat /data/claude/remote_control_url.txt`)
- Shown as a **persistent notification** in your Home Assistant dashboard

Open the URL in any browser or the Claude mobile app to control the running session remotely.

---

## Memory & Continuity

Claude Code always starts with `--continue` to resume the previous session.

A `CLAUDE.md` file is automatically created in your workspace on first run. It instructs Claude to:
- Read `MEMORY.md` at the start of every session to restore context
- Update `MEMORY.md` at the end of each session with tasks, preferences, and discoveries
- Mention remembered context proactively when relevant

This gives Claude persistent memory across restarts without any manual effort.

---

## Updates

When `AUTO_UPDATE_CHECK` is enabled (default), the add-on checks npm for a newer `@anthropic-ai/claude-code` version on every startup. If a new version is found, it downloads and installs it once — the binary lives in `/data/claude/npm-global` (persistent storage) and is reused on subsequent restarts.

**To force a manual update:** disable `AUTO_UPDATE_CHECK`, restart, re-enable it, restart again.

---

## Web Terminal

The **Open Web UI** button opens a full bash terminal in your browser (via ttyd). Use it to:
- Run `claude login` for first-time authentication
- Approve Telegram pairing codes
- Inspect workspace files
- Run `claude` interactively for debugging
- Check `cat /data/claude/remote_control_url.txt` for the latest remote control URL

---

## Copying credentials from another machine

If you already use Claude Code on your Mac or PC and want to skip `claude login` on the device, copy your credentials directly:

```bash
# Run this on your Mac/PC:
scp ~/.claude/.credentials.json \
  root@homeassistant.local:/data/addon_data/local_claude-code/claude/.claude/
```

Then restart the add-on — it will detect the credentials and proceed directly to the daemon startup.
