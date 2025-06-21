from fastapi import APIRouter, HTTPException
import logging

from models import ScriptResponse
from services import get_service_manager, get_ha_client, get_ngrok_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scripts", tags=["scripts"])

@router.get("/")
async def get_scripts():
    """
    Get list of available scripts from Home Assistant.
    """
    try:
        ha_client = get_ha_client()
        
        scripts = await ha_client.get_scripts_async()
        return {
            "scripts": scripts,
            "count": len(scripts)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting scripts: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while retrieving scripts"
        )

@router.get("/{script_id}")
async def get_script(script_id: str):
    """
    Get information about a specific script.
    """
    try:
        ha_client = get_ha_client()
        
        script_info = await ha_client.get_script_async(script_id)
        
        if not script_info:
            raise HTTPException(
                status_code=404, 
                detail=f"Script '{script_id}' not found in Home Assistant"
            )
        
        return script_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting script {script_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while retrieving script"
        )

@router.get("/run/{script_id}")
async def run_script(script_id: str):
    """
    Execute a script via the tunnel.
    This endpoint is accessible through the ngrok tunnel.
    """
    try:
        ha_client = get_ha_client()
        
        # Execute the script in Home Assistant
        result = await ha_client.run_script_async(script_id)
        
        logger.info(f"✅ Script {script_id} executed successfully")
        
        return ScriptResponse(
            success=True,
            message=f"Script {script_id} executed successfully",
            script_id=script_id,
            result=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error running script {script_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while executing script"
        ) 