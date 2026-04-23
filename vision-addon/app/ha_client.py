import os
import aiohttp
import logging

logger = logging.getLogger(__name__)

# Prefer the real HA URL for LLAT compatibility; fall back to supervisor proxy
HA_URL = os.environ.get("HA_URL", "http://homeassistant:8123")
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


async def fire_event(event_type: str, data: dict):
    url = f"{HA_URL}/api/events/{event_type}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=HEADERS) as resp:
                if resp.status != 200:
                    logger.warning(f"HA event {event_type} returned {resp.status}")
    except Exception as e:
        logger.error(f"Failed to fire HA event {event_type}: {e}")


async def set_state(entity_id: str, state: str, attributes: dict = None):
    url = f"{HA_URL}/api/states/{entity_id}"
    payload = {"state": state, "attributes": attributes or {}}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=HEADERS) as resp:
                if resp.status not in (200, 201):
                    logger.warning(f"HA set_state {entity_id} returned {resp.status}")
    except Exception as e:
        logger.error(f"Failed to set HA state {entity_id}: {e}")


async def set_last_gesture(gesture: str):
    await set_state(
        "sensor.vision_last_gesture",
        gesture,
        {"friendly_name": "Vision Last Gesture", "icon": "mdi:hand-wave"},
    )


async def update_sensors(faces_count: int, person_states: dict, motion: bool):
    await set_state(
        "sensor.vision_faces_count",
        str(faces_count),
        {"friendly_name": "Vision Faces Count", "icon": "mdi:account-multiple"},
    )
    await set_state(
        "binary_sensor.vision_motion",
        "on" if motion else "off",
        {"friendly_name": "Vision Motion", "device_class": "motion"},
    )
    for name, detected in person_states.items():
        entity_id = f"binary_sensor.vision_person_{name.lower().replace(' ', '_')}"
        await set_state(
            entity_id,
            "on" if detected else "off",
            {"friendly_name": f"Vision Person {name}", "device_class": "presence"},
        )
