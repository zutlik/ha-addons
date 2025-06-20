# app/app.py
import os
from fastapi import FastAPI
import logging

# Set up basic logging for the add-on
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app_logger = logging.getLogger(__name__)

app = FastAPI()

# Hardcoded Home Assistant script entity ID
# This should be updated to match your actual script entity ID
HA_SCRIPT_ENTITY_ID = "light.switcher_light_1326_light_1"

# Get the Home Assistant token from environment variables
# This will be injected by run.sh from add-on options
HA_TOKEN = os.environ.get('HOME_ASSISTANT_TOKEN')

# Home Assistant API base URL
HA_BASE_URL = "http://supervisor/core/api"

# Validate that the token is available
if not HA_TOKEN:
    app_logger.error("HOME_ASSISTANT_TOKEN environment variable is not set!")
    app_logger.error("Please configure the add-on with a valid Home Assistant token.")
else:
    app_logger.info(f"Home Assistant Token (first 5 chars): {HA_TOKEN[:5]}...")
    app_logger.info(f"Hardcoded Script Entity ID: {HA_SCRIPT_ENTITY_ID}")

app_logger.info(f"Home Assistant Base URL: {HA_BASE_URL}")

@app.get("/")
async def read_root():
    """
    A simple root endpoint to confirm the FastAPI server is running.
    """
    app_logger.info("Root endpoint called.")
    return {
        "message": "Hello from FastAPI Shell Command Executor Add-on!",
        "script_entity_id": HA_SCRIPT_ENTITY_ID,
        "token_configured": bool(HA_TOKEN),
        "ha_base_url": HA_BASE_URL
    }

@app.get("/api/status")
async def get_status():
    """
    Get the current status of the add-on configuration.
    """
    return {
        "script_entity_id": HA_SCRIPT_ENTITY_ID,
        "token_configured": bool(HA_TOKEN),
        "ha_base_url": HA_BASE_URL
    }

# You will add more endpoints here in later tasks, like:
# @app.post("/api/start_ngrok_tunnel")
# async def start_ngrok_tunnel(request: Request):
#     # ... implementation for ngrok tunnel ...
#     pass

# @app.get("/api/list_ha_scripts")
# async def list_ha_scripts():
#     # ... implementation to list HA scripts ...
#     pass
