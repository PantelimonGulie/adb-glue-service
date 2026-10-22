from urllib.parse import urlsplit

from fastapi import HTTPException, Request


def same_origin_request(request: Request) -> None:
    if request.method in ("GET", "HEAD"):
        return
    # A cross-site form cannot add this header, and a cross-site script needs a CORS
    # preflight that this service never grants.
    origin = request.headers.get("origin")
    if request.headers.get("x-glue-request") != "1" or (
        origin and urlsplit(origin).netloc != request.url.netloc
    ):
        raise HTTPException(403, "only the dashboard may do this")
