from fastapi import APIRouter, Depends

from glue.api import (
    activity,
    admin,
    analytics,
    assistant,
    demo,
    events,
    orders,
    overview,
    review,
    session,
    stock,
)
from glue.guard import same_origin_request

router = APIRouter(prefix="/api", dependencies=[Depends(same_origin_request)])
router.include_router(session.router)
router.include_router(demo.router)
router.include_router(admin.router)
router.include_router(overview.router)
router.include_router(orders.router)
router.include_router(stock.router)
router.include_router(review.router)
router.include_router(activity.router)
router.include_router(analytics.router)
router.include_router(assistant.router)
router.include_router(events.router)
