import hashlib
import hmac

HEADER = "x-signature"


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def event_message(event_id: str, body: bytes) -> bytes:
    # The receiver dedupes on the event id; signed with the body, a captured body cannot come
    # back under a fresh id.
    return event_id.encode() + b"\n" + body


def headers(secret: str, body: bytes) -> dict[str, str]:
    return {"content-type": "application/json", HEADER: sign(secret, body)}


def verify(secret: str, body: bytes, signature: str | None) -> bool:
    # An unset secret must not verify anything, or a missing env var would accept every body.
    if not secret or signature is None:
        return False
    return hmac.compare_digest(sign(secret, body), signature)
