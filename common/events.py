import json
import logging

import httpx

from common import signing

log = logging.getLogger(__name__)


async def emit(
    http: httpx.AsyncClient,
    url: str,
    event_type: str,
    data: dict,
    event_id: str,
    source: str,
    secret: str,
) -> None:
    body = json.dumps({"type": event_type, "data": data}).encode()
    headers = {"x-adobe-event-id": event_id, "x-source": source, **signing.headers(secret, body)}
    try:
        response = await http.post(url, content=body, headers=headers, timeout=2)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("%s event %s not delivered to %s: %s", event_type, event_id, url, exc)
