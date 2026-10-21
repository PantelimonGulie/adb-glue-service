import logging

import httpx

log = logging.getLogger(__name__)


async def emit(
    http: httpx.AsyncClient, url: str, event_type: str, data: dict, event_id: str, source: str
) -> None:
    headers = {"x-adobe-event-id": event_id, "x-source": source}
    try:
        response = await http.post(
            url, json={"type": event_type, "data": data}, headers=headers, timeout=2
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("%s event %s not delivered to %s: %s", event_type, event_id, url, exc)
