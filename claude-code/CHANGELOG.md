# Changelog

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
