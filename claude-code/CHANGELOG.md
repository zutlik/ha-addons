# Changelog

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
