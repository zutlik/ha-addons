# app/app.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import logging
import asyncio
from typing import Dict, Any, Optional
import json

from ngrok_manager import NgrokManager
from ha_client import HomeAssistantClient
from models import ScriptRequest, ScriptResponse, TunnelResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Home Assistant Script Publisher", version="1.0.0")

# Initialize managers
ngrok_manager = NgrokManager()
ha_client = HomeAssistantClient()

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting Home Assistant Script Publisher...")
    
    # Validate configuration
    if not ngrok_manager.ngrok_token:
        logger.error("NGROK_AUTH_TOKEN not configured!")
        logger.error("Please configure the add-on with a valid ngrok authentication token.")
    
    if not ha_client.is_configured():
        logger.error("Home Assistant configuration not found!")
        logger.error("Please configure the add-on with Home Assistant URL and token.")

@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Home Assistant Script Publisher",
        "version": "1.0.0",
        "status": "running",
        "ngrok_configured": bool(ngrok_manager.ngrok_token),
        "ha_configured": ha_client.is_configured()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/create_tunnel", response_model=TunnelResponse)
async def create_tunnel(script_request: ScriptRequest, background_tasks: BackgroundTasks):
    """
    Create a new ngrok tunnel for a specific script.
    """
    try:
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
            raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found in Home Assistant")
        
        # Start ngrok tunnel
        tunnel_url = ngrok_manager.start_tunnel_subprocess(8000, ngrok_manager.ngrok_token)
        
        if not tunnel_url:
            raise HTTPException(status_code=500, detail="Failed to create ngrok tunnel")
        
        # Store tunnel information
        tunnel_info = {
            'tunnel_url': tunnel_url,
            'script_id': script_id,
            'created_at': asyncio.get_event_loop().time()
        }
        
        ngrok_manager.add_tunnel(script_id, tunnel_info)
        
        # Get the complete URL
        complete_url = ngrok_manager.get_complete_url_for_script(script_id)
        
        logger.info(f"Created tunnel for script {script_id}: {tunnel_url}")
        logger.info(f"Complete URL: {complete_url}")
        
        return TunnelResponse(
            success=True,
            message=f"Tunnel created successfully for script {script_id}",
            tunnel_url=tunnel_url,
            complete_url=complete_url,
            script_id=script_id
        )
        
    except Exception as e:
        logger.error(f"Error creating tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/run_script/{script_id}")
async def run_script(script_id: str):
    """
    Execute a script via the tunnel.
    This endpoint is accessible through the ngrok tunnel.
    """
    try:
        # Validate that this script has an active tunnel
        if not ngrok_manager.is_tunnel_active_for_script(script_id):
            raise HTTPException(status_code=404, detail=f"No active tunnel found for script {script_id}")
        
        # Execute the script in Home Assistant
        result = await ha_client.run_script_async(script_id)
        
        return ScriptResponse(
            success=True,
            message=f"Script {script_id} executed successfully",
            script_id=script_id,
            result=result
        )
        
    except Exception as e:
        logger.error(f"Error running script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tunnels")
async def get_tunnels():
    """
    Get information about all active tunnels.
    """
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

@app.get("/tunnel/{script_id}")
async def get_tunnel(script_id: str):
    """
    Get information about a specific tunnel.
    """
    tunnel_info = ngrok_manager.get_tunnel_by_script_id(script_id)
    
    if not tunnel_info:
        raise HTTPException(status_code=404, detail=f"No tunnel found for script {script_id}")
    
    return {
        'script_id': script_id,
        'tunnel_url': tunnel_info.get('tunnel_url'),
        'complete_url': tunnel_info.get('complete_url'),
        'created_at': tunnel_info.get('created_at')
    }

@app.delete("/tunnel/{script_id}")
async def delete_tunnel(script_id: str):
    """
    Delete a specific tunnel.
    """
    tunnel_info = ngrok_manager.get_tunnel_by_script_id(script_id)
    
    if not tunnel_info:
        raise HTTPException(status_code=404, detail=f"No tunnel found for script {script_id}")
    
    # Remove from active tunnels
    ngrok_manager.remove_tunnel(script_id)
    
    # If this was the last tunnel, stop ngrok process
    if ngrok_manager.get_tunnel_count() == 0:
        ngrok_manager.stop_tunnel()
    
    return {
        "success": True,
        "message": f"Tunnel for script {script_id} deleted successfully"
    }

@app.delete("/tunnels")
async def delete_all_tunnels():
    """
    Delete all active tunnels.
    """
    tunnel_count = ngrok_manager.get_tunnel_count()
    
    # Clear all tunnels
    ngrok_manager.clear_all_tunnels()
    
    # Stop ngrok process
    ngrok_manager.stop_tunnel()
    
    return {
        "success": True,
        "message": f"All {tunnel_count} tunnels deleted successfully"
    }

@app.get("/scripts")
async def get_scripts():
    """
    Get all available scripts from Home Assistant.
    """
    try:
        scripts = await ha_client.get_scripts_async()
        return {"scripts": scripts}
    except Exception as e:
        logger.error(f"Error getting scripts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/script/{script_id}")
async def get_script(script_id: str):
    """
    Get information about a specific script.
    """
    try:
        script_info = await ha_client.get_script_async(script_id)
        if not script_info:
            raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")
        return script_info
    except Exception as e:
        logger.error(f"Error getting script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
