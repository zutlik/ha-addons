import os
import sys
from fastapi import APIRouter, HTTPException
import logging

from services import get_service_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

@router.get("/")
async def root():
    """Root endpoint with basic information."""
    service_manager = get_service_manager()
    status = service_manager.get_status()
    
    return {
        "message": "Home Assistant Script Publisher",
        "version": "1.0.0",
        "status": "running",
        "ngrok_configured": status["ngrok_configured"],
        "ha_configured": status["ha_configured"],
        "ha_connected": status["ha_connected"],
        "services_initialized": status["initialized"]
    }

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        service_manager = get_service_manager()
        status = service_manager.get_status()
        
        # Check if services are initialized
        if not status["initialized"]:
            raise HTTPException(status_code=503, detail="Services not initialized")
        
        # Check Home Assistant connectivity
        if not status["ha_connected"]:
            raise HTTPException(status_code=503, detail="Cannot connect to Home Assistant")
        
        return {
            "status": "healthy",
            "ngrok_available": status["ngrok_configured"],
            "ha_connected": status["ha_connected"],
            "services_initialized": status["initialized"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed") 

@router.get("/debug-paths")
def debug_paths():
    return {
        "cwd": os.getcwd(),
        "sys_path": sys.path,
        "files": os.listdir(".")
    } 