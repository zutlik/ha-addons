from fastapi import APIRouter, HTTPException, BackgroundTasks
import logging
import asyncio

from models import ScriptRequest, TunnelResponse
from services import get_ha_client, get_ngrok_manager, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tunnels", tags=["tunnels"])

@router.post("/create", response_model=TunnelResponse)
async def create_tunnel(script_request: ScriptRequest, background_tasks: BackgroundTasks):
    """
    Create a new ngrok tunnel for a specific script.
    """
    try:
        ngrok_manager = get_ngrok_manager()
        ha_client = get_ha_client()
        settings = get_settings()
        
        # Runtime validation
        if not ngrok_manager.is_configured():
            raise HTTPException(
                status_code=503, 
                detail="Ngrok not configured. Please add NGROK_AUTH_TOKEN to add-on configuration."
            )
        
        script_id = script_request.script_id
        
        # Check if tunnel already exists for this script
        if ngrok_manager.is_tunnel_active_for_script(script_id):
            existing_tunnel = ngrok_manager.get_tunnel_by_script_id(script_id)
            if existing_tunnel:
                return TunnelResponse(
                    success=True,
                    message=f"Tunnel already exists for script {script_id}",
                    tunnel_url=existing_tunnel.get('tunnel_url'),
                    complete_url=existing_tunnel.get('complete_url'),
                    script_id=script_id
                )
        
        # Validate script exists in Home Assistant
        if not await ha_client.script_exists_async(script_id):
            raise HTTPException(
                status_code=404, 
                detail=f"Script '{script_id}' not found in Home Assistant. Please check the script ID."
            )
        
        # Start ngrok tunnel using configurable port
        tunnel_url = ngrok_manager.start_tunnel_subprocess(settings.port, ngrok_manager.ngrok_token)
        
        if not tunnel_url:
            raise HTTPException(
                status_code=500, 
                detail="Failed to create ngrok tunnel. Please check your ngrok configuration."
            )
        
        # Store tunnel information
        tunnel_info = {
            'tunnel_url': tunnel_url,
            'script_id': script_id,
            'created_at': asyncio.get_event_loop().time()
        }
        
        ngrok_manager.add_tunnel(script_id, tunnel_info)
        
        # Get the complete URL
        complete_url = ngrok_manager.get_complete_url_for_script(script_id)
        
        logger.info(f"✅ Created tunnel for script {script_id}: {tunnel_url}")
        logger.info(f"🔗 Complete URL: {complete_url}")
        logger.info(f"📡 Forwarding to port: {settings.port}")
        
        return TunnelResponse(
            success=True,
            message=f"Tunnel created successfully for script {script_id}",
            tunnel_url=tunnel_url,
            complete_url=complete_url,
            script_id=script_id
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"❌ Error creating tunnel: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while creating tunnel"
        )

@router.get("/")
async def get_tunnels():
    """
    Get information about all active tunnels.
    """
    try:
        ngrok_manager = get_ngrok_manager()
        
        tunnels = ngrok_manager.get_active_tunnels()
        
        # Format response with complete URLs
        tunnel_list = []
        for script_id, tunnel_info in tunnels.items():
            tunnel_list.append({
                'script_id': script_id,
                'tunnel_url': tunnel_info.get('tunnel_url'),
                'complete_url': tunnel_info.get('complete_url'),
                'created_at': tunnel_info.get('created_at')
            })
        
        return {
            "tunnels": tunnel_list,
            "count": len(tunnel_list)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting tunnels: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while retrieving tunnels"
        )

@router.get("/{script_id}")
async def get_tunnel(script_id: str):
    """
    Get information about a specific tunnel.
    """
    try:
        ngrok_manager = get_ngrok_manager()
        
        tunnel_info = ngrok_manager.get_tunnel_by_script_id(script_id)
        
        if not tunnel_info:
            raise HTTPException(
                status_code=404, 
                detail=f"No tunnel found for script {script_id}"
            )
        
        return {
            'script_id': script_id,
            'tunnel_url': tunnel_info.get('tunnel_url'),
            'complete_url': tunnel_info.get('complete_url'),
            'created_at': tunnel_info.get('created_at')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting tunnel for {script_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while retrieving tunnel"
        )

@router.delete("/{script_id}")
async def delete_tunnel(script_id: str):
    """
    Delete a specific tunnel.
    """
    try:
        ngrok_manager = get_ngrok_manager()
        
        tunnel_info = ngrok_manager.get_tunnel_by_script_id(script_id)
        
        if not tunnel_info:
            raise HTTPException(
                status_code=404, 
                detail=f"No tunnel found for script {script_id}"
            )
        
        # Remove from active tunnels
        ngrok_manager.remove_tunnel(script_id)
        
        # If this was the last tunnel, stop ngrok process
        if ngrok_manager.get_tunnel_count() == 0:
            ngrok_manager.stop_tunnel()
        
        logger.info(f"✅ Tunnel for script {script_id} deleted successfully")
        
        return {
            "success": True,
            "message": f"Tunnel for script {script_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting tunnel for {script_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while deleting tunnel"
        )

@router.delete("/")
async def delete_all_tunnels():
    """
    Delete all active tunnels.
    """
    try:
        ngrok_manager = get_ngrok_manager()
        
        tunnel_count = ngrok_manager.get_tunnel_count()
        
        if tunnel_count == 0:
            return {
                "success": True,
                "message": "No active tunnels to delete"
            }
        
        # Stop all tunnels
        ngrok_manager.stop_tunnel()
        
        # Clear all tunnels from the active tunnels list
        ngrok_manager.clear_all_tunnels()
        
        logger.info(f"✅ Deleted {tunnel_count} active tunnels")
        
        return {
            "success": True,
            "message": f"Deleted {tunnel_count} active tunnels"
        }
        
    except Exception as e:
        logger.error(f"❌ Error deleting all tunnels: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Internal server error while deleting tunnels"
        ) 