from fastapi import APIRouter, Depends

from glue.api import demo, session
from glue.guard import same_origin_request

router = APIRouter(prefix="/api", dependencies=[Depends(same_origin_request)])
router.include_router(session.router)
router.include_router(demo.router)
