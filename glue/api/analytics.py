import csv
import io
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from glue import analytics, auth, ranges

router = APIRouter(dependencies=[Depends(auth.require("view"))])


def window_or_today(
    request: Request, window: Annotated[ranges.Window | None, Depends(ranges.from_query)]
) -> ranges.Window:
    zone = request.app.state.settings.zone
    return window or ranges.resolve("today", None, None, datetime.now(UTC), zone)


Window = Annotated[ranges.Window, Depends(window_or_today)]


@router.get("/analytics")
async def report(request: Request, window: Window, compare: bool = False) -> dict:
    return analytics.report(request.app.state.ctx, window, compare)


@router.get("/analytics.csv")
async def export(request: Request, window: Window) -> Response:
    text = io.StringIO()
    csv.writer(text).writerows(analytics.csv_rows(request.app.state.ctx, window))
    # from_query has already limited range to the known names, so it is safe in a header.
    name = request.query_params.get("range", "today")
    headers = {"Content-Disposition": f'attachment; filename="glue-flow-{name}.csv"'}
    return Response(text.getvalue(), media_type="text/csv", headers=headers)
