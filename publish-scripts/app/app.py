# app/app.py
import os
import asyncio
import requests
import subprocess
import time
import json
import threading
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import logging

# Set up basic logging for the add-on
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app_logger = logging.getLogger(__name__)

app = FastAPI()

# Hardcoded ngrok token for free tier
NGROK_TOKEN = "1ZnzMWMrIMjxpiPdW9xyUMreTgH_23T5WvNm3NRjBkQdrUGLK"

# Get the Home Assistant token from environment variables
# This will be injected by run.sh from add-on options
HA_TOKEN = os.environ.get('HOME_ASSISTANT_TOKEN')

# Get the Home Assistant base URL from environment variables
# Default to supervisor core API if not set
HA_BASE_URL = os.environ.get('HA_BASE_URL', 'http://supervisor/core/api')

# Fix the base URL if it contains /core/api (remove /core)
if HA_BASE_URL and '/core/api' in HA_BASE_URL:
    HA_BASE_URL = HA_BASE_URL.replace('/core/api', '/api')

# Validate that the token is available
if not HA_TOKEN:
    app_logger.error("HOME_ASSISTANT_TOKEN environment variable is not set!")
    app_logger.error("Please configure the add-on with a valid Home Assistant token.")
else:
    app_logger.info(f"Home Assistant Token (first 5 chars): {HA_TOKEN[:5]}...")

app_logger.info(f"Home Assistant Base URL: {HA_BASE_URL}")
app_logger.info(f"ngrok Token configured: {bool(NGROK_TOKEN)}")

# Global variable to store active tunnel info
active_tunnel_info = None
ngrok_process = None

def start_ngrok_tunnel_subprocess(port, token):
    """
    Start ngrok tunnel using subprocess (command line).
    This is more reliable than the Python SDK.
    """
    global ngrok_process
    
    try:
        # Kill any existing ngrok processes
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
        time.sleep(1)
        
        # Start ngrok tunnel
        cmd = ['ngrok', 'http', str(port), '--log=stdout']
        if token:
            cmd.extend(['--authtoken', token])
        
        ngrok_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for ngrok to start
        time.sleep(3)
        
        # Get tunnel URL from ngrok API
        try:
            response = requests.get('http://localhost:4040/api/tunnels', timeout=5)
            if response.status_code == 200:
                tunnels = response.json()['tunnels']
                if tunnels:
                    return tunnels[0]['public_url']
                else:
                    raise Exception("No tunnels found")
            else:
                raise Exception(f"Failed to get tunnel info: {response.status_code}")
        except Exception as e:
            # If API fails, try to parse from ngrok output
            if ngrok_process.poll() is None:
                # Process is still running, try to get URL from logs
                time.sleep(2)
                try:
                    response = requests.get('http://localhost:4040/api/tunnels', timeout=5)
                    if response.status_code == 200:
                        tunnels = response.json()['tunnels']
                        if tunnels:
                            return tunnels[0]['public_url']
                except:
                    pass
            
            raise Exception(f"Failed to get tunnel URL: {e}")
            
    except Exception as e:
        if ngrok_process:
            ngrok_process.terminate()
            ngrok_process = None
        raise e

def stop_ngrok_tunnel():
    """
    Stop the active ngrok tunnel.
    """
    global ngrok_process, active_tunnel_info
    
    try:
        if ngrok_process:
            ngrok_process.terminate()
            ngrok_process.wait(timeout=5)
            ngrok_process = None
        
        # Also kill any ngrok processes
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
        
        active_tunnel_info = None
        return True
    except Exception as e:
        app_logger.error(f"Failed to stop ngrok tunnel: {e}")
        return False

# Pydantic model for tunnel creation request
class TunnelRequest(BaseModel):
    port: int = 8099  # Default to the app's port
    name: str = "publish-scripts-tunnel"
    script_id: Optional[str] = None  # Optional script ID to run via the tunnel

# Pydantic model for tunnel response
class TunnelResponse(BaseModel):
    success: bool
    tunnel_url: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None

# Pydantic model for script execution response
class ScriptResponse(BaseModel):
    success: bool
    message: str
    script_id: str
    error: Optional[str] = None

class StartNgrokTunnelRequest(BaseModel):
    script_id: str
    port: int = 8099
    name: str = "publish-scripts-tunnel"

class StopNgrokTunnelRequest(BaseModel):
    script_id: str

def call_home_assistant_api(service: str, data: Optional[dict] = None) -> dict:
    """
    Make a call to the Home Assistant API to execute services.
    """
    if not HA_TOKEN:
        raise Exception("Home Assistant token not configured")
    
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = data or {}
    
    url = f"{HA_BASE_URL}/services/{service}"
    app_logger.info(f"Calling Home Assistant API: {url}")
    app_logger.info(f"Payload: {payload}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        app_logger.error(f"Home Assistant API call failed: {e}")
        raise Exception(f"Failed to call Home Assistant API: {e}")

def run_ha_script(script_id: str) -> dict:
    """
    Execute a Home Assistant script by its entity ID.
    """
    app_logger.info(f"Executing Home Assistant script: {script_id}")
    
    # Call the script.turn_on service with the script entity ID
    payload = {"entity_id": script_id}
    return call_home_assistant_api("script/turn_on", payload)

@app.get("/")
async def read_root():
    """
    A simple root endpoint to confirm the FastAPI server is running.
    """
    app_logger.info("Root endpoint called.")
    return {
        "message": "Hello from Publish Scripts Add-on!",
        "token_configured": bool(HA_TOKEN),
        "ha_base_url": HA_BASE_URL,
        "ngrok_configured": bool(NGROK_TOKEN),
        "endpoints": {
            "run_script": "/api/run_script/{script_id}",
            "start_tunnel": "/api/start_ngrok_tunnel",
            "list_tunnels": "/api/ngrok_tunnels",
            "stop_tunnel": "/api/stop_ngrok_tunnel",
            "public_script": "/run_script/{script_id}"
        }
    }

@app.get("/api/status")
async def get_status():
    """
    Get the current status of the add-on configuration.
    """
    return {
        "token_configured": bool(HA_TOKEN),
        "ha_base_url": HA_BASE_URL,
        "ngrok_configured": bool(NGROK_TOKEN)
    }

@app.get("/api/run_script/{script_id}", response_model=ScriptResponse)
async def execute_script(script_id: str):
    """
    Execute a Home Assistant script by its entity ID.
    """
    app_logger.info(f"Executing script: {script_id}")
    
    try:
        result = run_ha_script(script_id)
        
        return ScriptResponse(
            success=True,
            message=f"Script {script_id} executed successfully",
            script_id=script_id
        )
    except Exception as e:
        app_logger.error(f"Failed to execute script {script_id}: {e}")
        return ScriptResponse(
            success=False,
            message=f"Failed to execute script {script_id}",
            script_id=script_id,
            error=str(e)
        )

@app.post("/api/start_ngrok_tunnel", response_model=TunnelResponse)
async def start_ngrok_tunnel_post(req: StartNgrokTunnelRequest):
    """
    Create an ngrok tunnel to expose the Home Assistant script execution endpoint.
    Uses subprocess to run ngrok command line tool. Accepts POST with JSON body.
    """
    global active_tunnel_info
    
    port = req.port
    name = req.name
    script_id = req.script_id
    
    app_logger.info(f"Starting ngrok tunnel for port {port}")
    
    try:
        # Check if we already have an active tunnel
        if active_tunnel_info and active_tunnel_info.get('tunnel_url'):
            tunnel_url = active_tunnel_info.get('tunnel_url')
            # Create the complete script execution URL
            complete_url = f"{tunnel_url}/run_script/{script_id}"
            return TunnelResponse(
                success=True,
                tunnel_url=complete_url,
                note="Using existing tunnel"
            )
        
        # Start ngrok tunnel using subprocess
        tunnel_url = start_ngrok_tunnel_subprocess(port, NGROK_TOKEN)
        
        app_logger.info(f"ngrok tunnel created successfully: {tunnel_url}")
        
        # Store tunnel info globally
        active_tunnel_info = {
            'tunnel_url': tunnel_url,
            'port': port,
            'script_id': script_id,
            'created_at': time.time()
        }
        
        # Create the complete script execution URL
        complete_url = f"{tunnel_url}/run_script/{script_id}"
        app_logger.info(f"Complete script execution URL: {complete_url}")
        
        # Free tier notes
        free_tier_note = "Free tier: URL changes on restart, 8-hour session limit"
        
        return TunnelResponse(
            success=True,
            tunnel_url=complete_url,
            note=free_tier_note
        )
        
    except Exception as e:
        error_msg = f"Failed to create ngrok tunnel: {str(e)}"
        app_logger.error(error_msg)
        return TunnelResponse(
            success=False,
            error=error_msg,
            note="Free tier limitations may apply"
        )

@app.get("/api/ngrok_tunnels")
async def list_ngrok_tunnels():
    """
    List all active ngrok tunnels.
    """
    global active_tunnel_info
    
    try:
        tunnel_list = []
        
        if active_tunnel_info and active_tunnel_info.get('tunnel_url'):
            tunnel_info = {
                "url": active_tunnel_info['tunnel_url'],
                "name": "publish-scripts-tunnel",
                "proto": "https",
                "addr": f"localhost:{active_tunnel_info.get('port', 8099)}",
                "status": "active",
                "script_id": active_tunnel_info.get('script_id'),
                "created_at": active_tunnel_info.get('created_at', 0)
            }
            tunnel_list.append(tunnel_info)
        
        return {
            "success": True,
            "tunnels": tunnel_list,
            "count": len(tunnel_list),
            "note": "Free tier: Limited concurrent tunnels"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tunnels: {str(e)}")

@app.post("/api/stop_ngrok_tunnel")
async def stop_ngrok_tunnel_endpoint(req: StopNgrokTunnelRequest):
    """
    Stop the active ngrok tunnel if it matches the provided script_id.
    """
    global active_tunnel_info
    
    try:
        # Check if there's an active tunnel and if the script_id matches
        if not active_tunnel_info:
            return {
                "success": False,
                "message": "No active ngrok tunnel found"
            }
        
        active_script_id = active_tunnel_info.get('script_id')
        if active_script_id != req.script_id:
            return {
                "success": False,
                "message": f"Script ID mismatch. Active tunnel is for script '{active_script_id}', but requested to stop for script '{req.script_id}'"
            }
        
        success = stop_ngrok_tunnel()
        
        if success:
            return {
                "success": True,
                "message": f"ngrok tunnel for script '{req.script_id}' stopped successfully"
            }
        else:
            return {
                "success": False,
                "message": "Failed to stop ngrok tunnel"
            }
            
    except Exception as e:
        error_msg = f"Failed to stop ngrok tunnel: {str(e)}"
        app_logger.error(error_msg)
        return {
            "success": False,
            "message": error_msg
        }

@app.get("/run_script/{script_id}")
async def public_script_execution(script_id: str):
    """
    Public endpoint to execute a Home Assistant script. Intended for ngrok tunnel exposure.
    """
    app_logger.info(f"[public_script_execution] Request received. Executing script: {script_id}")
    try:
        result = run_ha_script(script_id)
        return {
            "success": True,
            "message": f"Script {script_id} executed successfully via ngrok tunnel.",
            "script_id": script_id
        }
    except Exception as e:
        app_logger.error(f"[public_script_execution] Failed to execute script {script_id}: {e}")
        return {
            "success": False,
            "message": f"Failed to execute script {script_id}: {str(e)}",
            "script_id": script_id
        }

# You will add more endpoints here in later tasks, like:
# @app.get("/api/list_ha_scripts")
# async def list_ha_scripts():
#     # ... implementation to list HA scripts ...
#     pass
