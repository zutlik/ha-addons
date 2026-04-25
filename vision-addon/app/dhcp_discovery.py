"""HA WebSocket client that resolves a DHCP hostname to its current IP and
watches for IP changes.

The HA `dhcp/subscribe_discovery` command requires admin scope and pushes the
full address table on every change (no deltas). We scan each push for our
hostname and report a new IP if it differs from the last one we saw.
"""
import asyncio
import logging
from typing import Awaitable, Callable, Optional

import aiohttp

logger = logging.getLogger(__name__)


class DHCPDiscoveryError(Exception):
    pass


class DHCPDiscovery:
    def __init__(self, ha_url: str, token: str, hostname: str):
        # WebSocket URL is the HA REST base with http→ws + /api/websocket
        self._ws_url = ha_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
        self._token = token
        self._hostname = hostname
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._msg_id = 0
        self._last_ip: Optional[str] = None

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def _connect_and_auth(self) -> None:
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self._ws_url, heartbeat=30)

        # HA sends auth_required first
        hello = await self._ws.receive_json(timeout=10)
        if hello.get("type") != "auth_required":
            raise DHCPDiscoveryError(f"Unexpected hello: {hello}")

        await self._ws.send_json({"type": "auth", "access_token": self._token})
        auth_resp = await self._ws.receive_json(timeout=10)
        if auth_resp.get("type") != "auth_ok":
            raise DHCPDiscoveryError(f"WebSocket auth failed: {auth_resp}")

    async def _subscribe(self) -> int:
        sub_id = self._next_id()
        await self._ws.send_json({"id": sub_id, "type": "dhcp/subscribe_discovery"})

        # First message back is the result ack (success/failure of the subscribe).
        ack = await self._ws.receive_json(timeout=10)
        if ack.get("type") != "result" or not ack.get("success"):
            err = ack.get("error", {})
            raise DHCPDiscoveryError(
                f"dhcp/subscribe_discovery rejected (code={err.get('code')}): {err.get('message')}"
            )
        return sub_id

    def _find_ip(self, devices: list) -> Optional[str]:
        target = self._hostname.lower()
        matches = [d for d in devices if (d.get("hostname") or "").lower() == target]
        if not matches:
            return None
        if len(matches) > 1:
            macs = [d.get("mac_address") for d in matches]
            logger.warning(
                "Multiple DHCP entries for hostname %r (%s); using first.",
                self._hostname, macs,
            )
        return matches[0].get("ip_address")

    async def resolve(self, timeout: float) -> str:
        """Connect, subscribe, and wait up to `timeout` seconds for our hostname
        to appear. Returns the IP address. Leaves the connection open for
        watch() to use afterwards."""
        await self._connect_and_auth()
        await self._subscribe()

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise DHCPDiscoveryError(
                    f"Hostname {self._hostname!r} not found in DHCP discovery within {timeout:.0f}s"
                )
            try:
                msg = await self._ws.receive_json(timeout=remaining)
            except asyncio.TimeoutError:
                raise DHCPDiscoveryError(
                    f"Hostname {self._hostname!r} not found in DHCP discovery within {timeout:.0f}s"
                )

            event = msg.get("event") or {}
            devices = event.get("add") or []
            ip = self._find_ip(devices)
            if ip:
                self._last_ip = ip
                logger.info("Resolved %s → %s via HA DHCP discovery", self._hostname, ip)
                return ip

    async def watch(self, on_change: Callable[[str], Awaitable[None]]) -> None:
        """Run forever, calling on_change(new_ip) when the IP for our hostname
        changes. Caller is responsible for awaiting this in a background task."""
        assert self._ws is not None, "Call resolve() first"
        while True:
            try:
                msg = await self._ws.receive_json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error("DHCP WebSocket dropped: %s", e)
                raise

            event = msg.get("event") or {}
            devices = event.get("add") or []
            ip = self._find_ip(devices)
            if ip and ip != self._last_ip:
                logger.info(
                    "DHCP: %s IP changed %s → %s",
                    self._hostname, self._last_ip, ip,
                )
                self._last_ip = ip
                try:
                    await on_change(ip)
                except Exception:
                    logger.exception("on_change handler raised")

    async def close(self) -> None:
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._session is not None and not self._session.closed:
            await self._session.close()
