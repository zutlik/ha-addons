# app/app.py
import os
from fastapi import FastAPI
import logging

# Set up basic logging for the add-on
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app_logger = logging.getLogger(__name__)

app = FastAPI()

# Get the Home Assistant token from environment variables
# This will be injected by run.sh from add-on options
HA_TOKEN = os.environ.get('HOME_ASSISTANT_TOKEN')
app_logger.info(f"Home Assistant Token (first 5 chars): {HA_TOKEN[:5] if HA_TOKEN else 'Not set'}")


@app.get("/")
async def read_root():
    """
    A simple root endpoint to confirm the FastAPI server is running.
    """
    app_logger.info("Root endpoint called.")
    return {"message": "Hello from FastAPI Shell Command Executor Add-on!"}

# You will add more endpoints here in later tasks, like:
# @app.post("/api/start_ngrok_tunnel")
# async def start_ngrok_tunnel(request: Request):
#     # ... implementation for ngrok tunnel ...
#     pass

# @app.get("/api/list_ha_scripts")
# async def list_ha_scripts():
#     # ... implementation to list HA scripts ...
#     pass
