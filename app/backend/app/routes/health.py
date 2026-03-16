"""Health and inventory API routes.

Design doc reference: §27 (health/inventory refresh model).
"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def list_health(request: Request):
    health_service = request.app.state.health_service
    return health_service.get_health_summary()


@router.get("/inventory")
async def list_inventory(request: Request):
    health_service = request.app.state.health_service
    return health_service.get_inventory_summary()


@router.post("/health/refresh")
async def refresh_health(request: Request):
    health_service = request.app.state.health_service
    await health_service.refresh_all_health()
    return health_service.get_health_summary()


@router.post("/inventory/refresh")
async def refresh_inventory(request: Request):
    health_service = request.app.state.health_service
    await health_service.refresh_all_inventory()
    return health_service.get_inventory_summary()
