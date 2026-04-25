"""On-demand DHCP discovery against HA's WebSocket API.

Connects, subscribes to ``dhcp/subscribe_discovery``, reads the first push
(which always contains the full address table), returns the IP for the
requested hostname, and closes the WebSocket.

Used both at startup and as the recovery path when the camera stream stalls.
There is intentionally no long-lived state — every call opens a fresh
connection.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class DHCPDiscoveryError(Exception):
    pass


def _ws_url(ha_url: str) -> str:
    return ha_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"


async def resolve_hostname_ip(
    ha_url: str,
    token: str,
    hostname: str,
    timeout: float = 10.0,
) -> str:
    """Resolve ``hostname`` to its current IP via HA's DHCP discovery.

    Raises :class:`DHCPDiscoveryError` if HA cannot be reached, the token is
    rejected, the subscribe is denied, or the hostname is not in the address
    table within ``timeout`` seconds.
    """
    target = hostname.lower()
    url = _ws_url(ha_url)
    session = aiohttp.ClientSession()
    try:
        try:
            ws = await session.ws_connect(url, heartbeat=30)
        except aiohttp.ClientError as e:
            raise DHCPDiscoveryError(f"Cannot reach HA WebSocket at {url}: {e}") from e

        try:
            hello = await ws.receive_json(timeout=10)
            if hello.get("type") != "auth_required":
                raise DHCPDiscoveryError(f"Unexpected hello: {hello}")

            await ws.send_json({"type": "auth", "access_token": token})
            auth_resp = await ws.receive_json(timeout=10)
            if auth_resp.get("type") != "auth_ok":
                raise DHCPDiscoveryError(f"WebSocket auth failed: {auth_resp}")

            await ws.send_json({"id": 1, "type": "dhcp/subscribe_discovery"})
            ack = await ws.receive_json(timeout=10)
            if ack.get("type") != "result" or not ack.get("success"):
                err = ack.get("error", {})
                raise DHCPDiscoveryError(
                    f"dhcp/subscribe_discovery rejected (code={err.get('code')}): "
                    f"{err.get('message')}"
                )

            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise DHCPDiscoveryError(
                        f"Hostname {hostname!r} not found in DHCP discovery within {timeout:.0f}s"
                    )
                try:
                    msg = await ws.receive_json(timeout=remaining)
                except asyncio.TimeoutError:
                    raise DHCPDiscoveryError(
                        f"Hostname {hostname!r} not found in DHCP discovery within {timeout:.0f}s"
                    )

                event = msg.get("event") or {}
                devices = event.get("add") or []
                matches = [d for d in devices if (d.get("hostname") or "").lower() == target]
                if not matches:
                    continue
                if len(matches) > 1:
                    macs = [d.get("mac_address") for d in matches]
                    logger.warning(
                        "Multiple DHCP entries for hostname %r (%s); using first.",
                        hostname, macs,
                    )
                return matches[0].get("ip_address")
        finally:
            try:
                await ws.close()
            except Exception:
                pass
    finally:
        try:
            await session.close()
        except Exception:
            pass
