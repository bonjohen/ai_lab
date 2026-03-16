"""Source listing API routes.

Design doc reference: §16 — list sources, get source detail.
"""

from fastapi import APIRouter, HTTPException, Request

from app.config.views import build_source_detail, build_source_list
from app.models.views import SourceDetail, SourceListItem

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceListItem])
async def list_sources(request: Request) -> list[SourceListItem]:
    config = request.app.state.config
    return build_source_list(config)


@router.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(source_id: str, request: Request) -> SourceDetail:
    config = request.app.state.config
    detail = build_source_detail(config, source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
    return detail
