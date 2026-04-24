# Changelog

## v1.10.12 - Fix HA MCP server location: write to user-level settings
- Claude Code loads MCP servers from `$HOME/.claude/settings.json` (user-level),
  not from the project `.claude/settings.json`. Fixed run.sh to write the MCP
  config to the user-level file; also writes project-level as belt-and-suspenders.

## v1.10.11 - Fix HA MCP token: write real value, refresh on every restart
- Claude Code's SSE `headers` do not support `${VAR}` env-var substitution,
  so the `${SUPERVISOR_TOKEN}` placeholder written in v1.10.10 never connected.
- Fixed: the validated token from `.supervisor_token` is now written directly
  into settings.json on every addon restart (not just first install). This
  also keeps the token current if the LLAT is rotated.

## v1.10.10 - Auto-configure HA MCP server on startup
- On each startup, `run.sh` now ensures the HA MCP server is configured in
  `$WORK_DIR/.claude/settings.json`. This gives Claude structured tool access
  to Home Assistant (entity queries, service calls, logbook, etc.) without
  needing raw curl commands.
- MCP endpoint is always `http://homeassistant:8123/mcp_server/sse` — the
  supervisor proxy does not expose `/mcp_server`, so this is hardcoded
  independently of the selected token/URL.
- Token is referenced as `${SUPERVISOR_TOKEN}` (env-var placeholder) — Claude
  Code substitutes it from the tmux environment at runtime; no token is
  hardcoded in the settings file.
- Existing `homeassistant` MCP entries are never overwritten, so user
  customisations survive restarts and upgrades.
- Requires HA 2024.11+ (MCP server built into HA core; no separate addon needed).

## v1.10.9 - Fix --continue to always resume large sessions
- Removed the 400-line session file size gate that incorrectly prevented
  resuming long-but-valid sessions after a restart.
- Replaced with a targeted check: inspect the last 20 lines of the session
  JSONL for an unresolved trailing `tool_use` (no following `tool_result`),
  which is the actual cause of resume crashes after unclean shutdowns.
- Large sessions with clean state now always resume with `--continue`.
  Corrupt sessions (pending tool call) skip `--continue` preemptively;
  all other resume failures are caught by the existing fast-exit fallback
  (< 15s exit drops to fresh-session mode for the rest of the boot).

## v1.10.8 - Validate HA token before use; dynamic HA_URL
- `run.sh` now actively tests each token against the HA Core API (`GET /api/`)
  before committing to it. If `SUPERVISOR_TOKEN` returns non-200 (common when
  `homeassistant_api: true` is not active in the running container), the addon
  automatically falls back to the user-supplied `HA_TOKEN` LLAT and switches
  the base URL to `http://homeassistant:8123`.
- Introduces `/data/claude/.ha_url`: a file written by `run.sh` alongside
  `.supervisor_token` that records the validated base URL. The tmux session and
  the persistent-notification curl call both read from this file instead of
  hardcoding `http://supervisor/core`.
- **Important for future sessions**: `SUPERVISOR_TOKEN` in the tmux environment
  may actually be a Long-Lived Access Token (LLAT), not the supervisor-injected
  JWT. `HA_URL` may be `http://homeassistant:8123` rather than
  `http://supervisor/core`. Always read both from `/data/claude/.ha_url` and
  `/data/claude/.supervisor_token` rather than assuming their values.

## v1.10.6 - Robust HA token fallback; add HA_TOKEN option
- `SUPERVISOR_TOKEN` is not always injected by the HA supervisor (depends on
  addon install state). Added a three-tier fallback: supervisor token → HA_TOKEN
  addon option → existing token file. This means a manually-written LLAT in
  `/data/claude/.supervisor_token` now survives restarts.
- Added optional `HA_TOKEN` config option: paste a Long-Lived Access Token
  (HA → Profile → Security → Long-Lived Access Tokens) and the addon uses it
  automatically when the supervisor token is unavailable.
- Never overwrite a valid existing token with an empty value on restart.

## v1.10.5 - bump version

## v1.10.0 - Seed workspace with self-improving-agent base files
- Bundle `CLAUDE.md`, `MEMORY.md`, `MEMORY_PROTOCOL.md`, `SKILLS_INDEX.md`,
  `SELF_IMPROVEMENT_PROTOCOL.md`, `IMPROVEMENTS_BACKLOG.md` in the image at
  `/opt/claude-base-files/`.
- On startup, copy each base file into `$WORK_DIR` only if it does not
  already exist — user edits on `/share` survive addon restart/upgrade.
- Replace the inline `CLAUDE.md` heredoc in `run.sh` with the seed loop.
  The new `CLAUDE.md` keeps the HA/RPi context and adds the session
  lifecycle + self-improvement mandate referenced by the other files.

## v1.9.6 - Pick latest URL, re-announce when it changes
- `head -1` was grabbing the *oldest* URL in tmux scrollback — so if
  claude printed the banner multiple times (reconnect, status refresh,
  previous --remote-control invocation in the same pane), we'd DM a
  long-expired URL with "This Remote Control session has ended."
- Use `tail -1` to pick the most recently rendered URL.
- Track LAST_URL instead of a one-shot POSTED flag, so if claude
  regenerates the URL during the daemon's lifetime we send a fresh DM
  + HA notification.

## v1.9.5 - Fix remote-control URL regex
- Claude prints the URL as `https://claude.ai/code/session_<id>`, not
  `/rc/<token>` — the old regex (carried over from an earlier CLI
  version) never matched, so the URL DM / HA notification never fired.
- Updated regex to match the current URL scheme.

## v1.9.4 - URL watcher diagnostics
- Telegram startup ping works in v1.9.3, but the URL DM still doesn't
  fire — meaning the URL isn't being found in the tmux pane.
- Watcher now logs capture-pane errors instead of swallowing stderr.
- After ~15s with no URL match, watcher dumps the last 60 lines of the
  pane to the add-on log (prefixed `[pane]`) so we can see what claude
  actually rendered vs. what our regex expects.

## v1.9.3 - Telegram startup ping + diagnostics
- Send a "Claude Code add-on starting up..." DM at the top of run.sh,
  before anything can go wrong with claude/URL extraction. Lets you
  confirm the Telegram token+chat_id pipe works independently.
- Log actual Telegram API response on failure instead of just "failed"
  (helps diagnose bad token, wrong chat_id, blocked bot, etc.).
- Log explicit reason when DM is disabled (missing token vs. missing
  chat_id), so add-on log tells you which option to fill in.
- Factor the sendMessage call into a `tg_send` helper reused by both
  the startup ping and the URL DM.

## v1.9.2 - Fix Telegram URL DM on startup
- Previous URL extraction tailed `tmux pipe-pane` output through sed.
  That failed because tmux streams partial terminal redraws (cursor
  positioning, clear-line) that can split the URL across what the sed
  filter sees as separate lines — so our regex never matched and the
  Telegram DM never fired.
- New approach: background watcher polls `tmux capture-pane -p` every 3s,
  which renders the pane to plain rendered text (no ANSI, no partial
  redraws). grep against that is reliable.
- Side effect: claude's live TUI output is no longer streamed into the
  add-on log. Use `claude-attach` from the Web UI to watch the daemon.

## v1.9.1 - Fix claude-attach password prompt
- The Web UI shell already runs as the claude user, so `su claude` inside
  claude-attach was prompting for claude's password. Skip the `su` when
  already running as claude; fall back to passwordless `sudo -u claude`
  only when invoked from a different user.

## v1.9.0 - Attachable claude daemon via tmux
- Daemon now runs inside a detached tmux session named `claude`. You can
  attach from the Web UI shell to interact with the live TUI — accept
  prompts, type messages, watch tool calls — then detach with Ctrl-b d
  without killing the daemon.
- New `claude-attach` helper: just run it in the Web UI shell. Falls back
  gracefully if no session is running.
- `claude-shell` prints a hint on launch when a daemon session is active.
- Replaces the `script -qefc` PTY wrapper with tmux, which doubles as both
  PTY provider (keeps claude in interactive mode) and attach surface.
- URL extraction still works: `tmux pipe-pane` streams pane output to
  /tmp/claude-pane.log, which a background `tail -F | sed` pipeline parses.
- Dockerfile adds `tmux` package; apparmor.txt allows the new
  /usr/local/bin/claude-attach binary.

## v1.8.2 - Drop automatic Telegram plugin setup
- Remove the TUI-driven plugin install/configure block from run.sh.
  It was brittle (timed keystrokes, `script` PTY wrapper, claude going
  conversational and ignoring `/exit`) and unreliable.
- The daemon still starts with `--channels plugin:telegram@claude-plugins-official`
  when TELEGRAM_BOT_TOKEN is set — the plugin just needs to be installed
  manually once via the Web UI (see DOCS.md for steps).
- Bot token and chat ID are still read from config for the startup URL DM.

## v1.8.1 - Default to Sonnet 4.6
- Daemon and Telegram setup now run with `--model claude-sonnet-4-6`
  instead of the (more expensive) Opus default.

## v1.8.0 - DAEMON_AUTOSTART flag for manual prompt acceptance
- New `DAEMON_AUTOSTART` config option (default true). When set to
  false, run.sh skips both the Telegram plugin setup and the claude
  daemon launch, leaving only ttyd running.
- Recovery flow when claude is blocked on a TUI prompt (trust dialog,
  bypass-permissions warning):
  1. Set `DAEMON_AUTOSTART: false`, restart add-on.
  2. Open the Web UI, run `claude --dangerously-skip-permissions`,
     accept the prompts.
  3. `/exit`, set `DAEMON_AUTOSTART: true`, restart.
- Claude persists the prompt acceptances to ~/.claude.json, so future
  daemon boots don't hit the prompts.

## v1.7.5 - Drive Telegram setup TUI with timed keystrokes
- v1.7.4 piped "2\n" upfront, but claude consumes stdin before rendering
  the TUI prompt — so the keystroke arrived at nothing.
- New approach: subshell with explicit sleeps that pace input to the
  PTY. Wait 6s for bootup, send down-arrow+Enter to select option 2
  (claude TUIs don't accept digit shortcuts), then slash commands with
  delays between them.
- Plugin install can take 20s (git clone + bun) so gave it room.

## v1.7.4 - Accept bypass-permissions prompt in Telegram setup
- Claude shows a second prompt on startup: "In Bypass Permissions mode...
  Yes, I accept" — our `bypassPermissionsModeAccepted` guess in
  .claude.json wasn't the right key. Prepend `2\n` to the Telegram
  plugin setup's stdin so the setup claude auto-selects "Yes, I accept".
- After setup runs once, claude should persist the acceptance to
  .claude.json so the daemon no longer hits the prompt. Log the
  top-level keys of .claude.json after setup so we can see the actual
  key name for future debugging.

## v1.7.3 - Pre-accept workspace trust + drop removed --no-color flag
- Claude on first launch in a workspace asks "Is this a project you
  trust?". Our headless daemon has no one to press 1, so it hung
  forever. Fix: pre-write `~/.claude.json` with `hasTrustDialogAccepted`
  and per-project `hasTrustDialogAccepted` set to true, merged with any
  existing config via `jq`.
- Claude Code removed/renamed the `--no-color` flag — Telegram plugin
  setup was exiting with "unknown option '--no-color'". Drop the flag,
  use `NO_COLOR=1` env var instead (de-facto standard).

## v1.7.2 - Actually install the Telegram plugin
- Earlier versions silently wrote the "Telegram plugin configured"
  marker even when `/plugin install` had failed (claude was exiting
  before processing the piped slash commands). So Telegram never
  actually worked — the daemon ran but the channels plugin wasn't
  installed or configured.
- Wrap the plugin-setup claude invocation in `script` (same PTY fix as
  v1.7.1) so slash commands actually process.
- Only write the marker if claude's exit code is 0; delete it on failure
  so we retry next boot.
- Marker now includes a SETUP_VERSION — bumping it forces re-run across
  upgrades. Current SETUP_VERSION=2, so v1.7.2 re-runs setup once even
  if your previous install wrote a v1-format marker.

## v1.7.1 - Give claude a pseudo-TTY so it doesn't fall into --print mode
- Without a TTY, claude auto-switches to --print mode and exits with
  "Input must be provided either through stdin or as a prompt argument".
- Wrap the claude invocation in `script -qefc ... /dev/null` to allocate
  a PTY, keeping claude in interactive/daemon mode for --channels and
  --remote-control.
- AppArmor: allow `/dev/ptmx` and `/dev/pts/**` for PTY allocation.

## v1.7.0 - DM the remote control URL to Telegram on each start
- New `TELEGRAM_CHAT_ID` option. When set alongside `TELEGRAM_BOT_TOKEN`,
  the add-on DMs the remote control URL to that chat every time claude
  starts.
- Uses the Telegram Bot API directly (`sendMessage`) from run.sh —
  doesn't route through Claude, so the URL is delivered even if
  claude itself is misbehaving.
- To find your chat ID, DM `@userinfobot` on Telegram.

## v1.6.1 - Prefer --continue, fall back on fast exit
- First launch of each boot tries `--continue` to resume the latest
  conversation. If claude exits in under 15s (stale deferred-tool
  marker or other corruption), drop `--continue` for the rest of this
  boot and start fresh sessions instead.
- On the common success path, claude resumes the latest conversation
  and keeps running — so you don't lose context on add-on restart.

## v1.6.0 - Stop claude crash bouncing the whole container
- Drop `--continue` from the daemon invocation. It was trying to resume
  sessions with stale deferred-tool markers (a side effect of the
  earlier crash loops) and exiting immediately with
  `No deferred tool marker found in the resumed session`.
  Cross-session context is handled by the CLAUDE.md / memory.md protocol,
  which does not depend on claude's internal session resume.
- Wrap the claude launch in a restart loop with a 10s cooldown so a
  claude crash no longer takes down the whole container — Web UI, ttyd
  session, and logs stay up while claude restarts.

## v1.5.0 - Web UI shell now runs as claude user
- ttyd previously spawned `bash` as root, so `claude: command not
  found` in the Web UI (root's PATH doesn't include the claude user's
  npm-global). Even worse, `claude login` would have written creds to
  the wrong HOME.
- Add `/usr/local/bin/claude-shell` wrapper that drops to claude with
  HOME=/data/claude, NPM_GLOBAL and PATH preconfigured, then execs
  bash. Point ttyd at it.
- `claude login` in the Web UI now writes to /data/claude/.claude/
  where run.sh looks for credentials on next boot.

## v1.4.0 - Fix install-from-empty and legacy perms
- Update check now branches on `command -v claude` first — if claude
  isn't installed, always install (prior logic silently treated
  INSTALLED="" and LATEST="" as "up to date" and skipped).
- Recursively `chmod -R a+rwX /data/claude` at root bootstrap so
  subdirs created by previous root-run boots are writable by the
  claude user (fixes `.env: Permission denied`).
- Better npm show failure handling: report and keep existing install
  rather than silently skipping.

## v1.3.0 - Fix su failure at the AppArmor layer
- Root cause of `su: cannot set groups: Operation not permitted`:
  apparmor.txt had a `# Capabilities` comment but no actual rules, so
  AppArmor denied every capability at the LSM layer regardless of what
  Docker/`full_access` granted.
- Add explicit `capability setuid,` / `setgid,` / `audit_write,` /
  `dac_override,` / `dac_read_search,` etc. so `su claude` can run
  setgroups() and PAM can set up the session.

## v1.2.0 - Fix su failure (setgroups EPERM)
- Previous `capabilities: [SETUID, SETGID]` in config.yaml was silently
  ignored — HA's schema uses `privileged:` and that allowlist does not
  include SETUID/SETGID. Swap to `full_access: true`, the only documented
  option that restores CAP_SETGID so `su claude` can run setgroups().
- Fixes: `su: cannot set groups: Operation not permitted` in add-on log
  that prevented Claude from ever starting on v1.0.9 and v1.1.0.

## v1.1.0 - Fix su and heredoc backtick expansion
- Add SETUID + SETGID capabilities to config.yaml so `su claude` works
- Move CLAUDE.md write outside the su heredoc block to its own
  single-quoted heredoc — backticks in the content no longer get
  executed by the outer shell
- Setup (npm install, .env) still runs as claude user via su

## v1.0.9 - Fix ownership without chown
- HA containers have no CAP_CHOWN — chown always fails even as root
- New strategy: mkdir /data/claude as root with chmod 777, then run
  all setup (npm install, config writes, CLAUDE.md) as the claude user
  via a su heredoc so every file is claude-owned from creation
- No chown calls anywhere in the script

## v1.0.8 - Move claude state to /data/claude/
- All claude-owned files now live under /data/claude/ (not /data/)
- /data is owned by HA Supervisor — we never chown it anymore
- Eliminates "Operation not permitted" errors on startup
- credentials, npm-global, channels, marker files all under /data/claude/

## v1.0.7 - Run claude as non-root user
- Create non-root `claude` user in image — fixes `--dangerously-skip-permissions` root rejection
- All `claude` invocations run via `su claude` with proper HOME/PATH environment
- Grant passwordless sudo so claude can escalate when needed
- Transfer /data and workspace ownership to claude user on startup

## v1.0.6 - Fix unknown option --cwd
- Replace `--cwd` (not a valid Claude Code flag) with `cd` before invoking claude

## v1.0.5 - Add --remote-control flag
- Start Claude daemon with `--remote-control` flag
- Session URL printed prominently in the add-on log with a clear banner
- Session URL saved to `/data/remote_control_url.txt`
- HA persistent notification updated with clickable link and copyable URL

## v1.0.4 - Updated setup documentation
- Rewrite DOCS.md to reflect the automated setup flow
- Step-by-step guide: configure → login via Web UI → restart → done
- Documents automatic Telegram plugin setup, pairing flow, and credentials copy shortcut

## v1.0.3 - Auto Telegram setup
- After first login, automatically runs plugin marketplace add → plugin install → /telegram:configure
- Uses marker file to skip setup on subsequent restarts (re-runs only if token changes)

## v1.0.2 - Fix plugin marketplace
- Add `git` and `openssh-client` to image — required for `claude /plugin marketplace add`

## v1.0.1 - Fix Web UI
- Switch to HA ingress with WebSocket streaming — fixes empty page on "Open Web UI"
- ttyd now receives correct base-path from HA ingress proxy

## v1.0.0 - Initial Release

- Persistent Claude Code daemon with `--continue` flag
- Smart update mechanism: stores binary in `/data/npm-global`, only downloads when a new version is available
- Telegram integration via native `--channels plugin:telegram@claude-plugins-official`
- Remote control session URL automatically captured, saved to `/data/remote_control_url.txt`, and shown as HA persistent notification
- Web terminal (ttyd) on port 7681 for first-time login and interactive access
- Auto-generated `CLAUDE.md` with memory protocol instructions
- Multi-architecture: aarch64 (Raspberry Pi), amd64
- OAuth-based authentication (Claude.ai subscription — no API key required)
