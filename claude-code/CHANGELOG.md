# Changelog

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
