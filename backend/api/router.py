"""
DataGhost – API router aggregator.
Mounts all sub-routers. Include this router in main.py with prefix="/api".
"""
from fastapi import APIRouter
from api.user_routes import router as user_router
from api.dlp_routes import router as dlp_router

from api.auth_routes import router as auth_router
from api.scan_routes import router as scan_router
from api.incident_routes import router as incident_router
from api.device_routes import router as device_router
from api.dashboard_routes import router as dashboard_router
from api.enrollment_routes import router as enrollment_router
from api.provisioning_routes import router as provisioning_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(scan_router)
router.include_router(incident_router)
router.include_router(device_router)
router.include_router(dashboard_router)
router.include_router(user_router)
router.include_router(dlp_router)
router.include_router(enrollment_router, prefix="/v1")
router.include_router(provisioning_router, prefix="/v1")
