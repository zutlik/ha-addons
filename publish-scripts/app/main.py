import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

# Add the current directory (app folder) to Python path to ensure imports work
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from fastapi.staticfiles import StaticFiles

from services import get_service_manager, get_ha_client, get_ngrok_manager
from settings import get_settings, Settings

# Import routers
from routers import health, tunnels, scripts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app(settings: Optional[Settings] = None) -> FastAPI:
    if settings is None:
        settings = get_settings() 

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan event handler for proper startup and shutdown."""
        # Get the service manager
        service_manager = get_service_manager()
        
        # Initialize services if not already done
        if not service_manager.is_initialized():
            service_manager.initialize_services()
        
        # Use the injected settings here
        app.state.settings = settings
        
        # Validate configuration on startup
        validate_startup_configuration()
        
        # Test Home Assistant connectivity
        # TODO: Update this to check the HA API is reachable
        # test_home_assistant_connectivity()  # Commented out for local development
        
        logger.info("✅ Publish Scripts add-on started successfully!")
        
        # TODO: Make sure the context manager is actually working and the ngrok is being stopped
        yield
        
        # Cleanup on shutdown
        ngrok_manager = get_ngrok_manager()
        if ngrok_manager:
            ngrok_manager.stop_cleanup_task()
            ngrok_manager.stop_tunnel()
            ngrok_manager.clear_all_tunnels()
        logger.info("🔄 Publish Scripts add-on shutting down...")

    app = FastAPI(
        title="Home Assistant Script Publisher", 
        version="1.0.0",
        lifespan=lifespan
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(tunnels.router)
    app.include_router(scripts.router)

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler for unhandled exceptions."""
        logger.error(f"❌ Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    # Add dynamic catch-all endpoint for /run/{unique_hash}
    @app.get("/run/{unique_hash}")
    async def run_script_by_hash(unique_hash: str, request: Request):
        ngrok_manager = get_ngrok_manager()
        if not ngrok_manager:
            raise HTTPException(status_code=503, detail="Ngrok manager not available.")
        
        script_id = ngrok_manager.get_script_id_by_hash(unique_hash)
        if not script_id:
            raise HTTPException(status_code=404, detail="Invalid or expired URL.")
        
        ha_client = get_ha_client()
        if not ha_client:
            raise HTTPException(status_code=503, detail="Home Assistant client not available.")
        
        try:
            result = await ha_client.run_script_async(script_id)
            return JSONResponse({
                "success": True,
                "message": f"Script {script_id} executed successfully",
                "script_id": script_id,
                "result": result
            })
        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": f"Failed to execute script: {e}",
                "script_id": script_id
            }, status_code=500)

    return app

def validate_startup_configuration():
    """Validate required configuration on startup."""
    logger.info("🔍 Validating add-on configuration...")
    
    service_manager = get_service_manager()
    
    # Check Home Assistant token
    ha_client = get_ha_client()
    if not ha_client or not ha_client.is_configured():
        logger.error("❌ HASSIO_TOKEN not configured!")
        logger.error("   Please configure the add-on with a valid Home Assistant token.")
        logger.error("   Go to Settings → Add-ons → Publish Scripts → Configuration")
        sys.exit(1)
    
    # Check Ngrok token (optional but recommended)
    ngrok_manager = get_ngrok_manager()
    if not ngrok_manager or not ngrok_manager.is_configured():
        logger.warning("⚠️  NGROK_AUTH_TOKEN not configured!")
        logger.warning("   Ngrok functionality will be disabled.")
        logger.warning("   To enable ngrok tunnels, add NGROK_AUTH_TOKEN to configuration.")
    else:
        logger.info("✅ Ngrok authentication token configured")
    
    logger.info("✅ Configuration validation passed")

def test_home_assistant_connectivity():
    """Test Home Assistant connectivity on startup."""
    logger.info("🔍 Testing Home Assistant connectivity...")
    
    try:
        ha_client = get_ha_client()
        if not ha_client:
            logger.error("❌ Home Assistant client not available!")
            return
        
        # Test basic connectivity
        if not ha_client.test_connection():
            logger.error("❌ Cannot connect to Home Assistant!")
            logger.error("   Please check your Home Assistant URL and token.")
            logger.error("   Make sure Home Assistant is running and accessible.")
            sys.exit(1)
        
        logger.info("✅ Home Assistant connectivity test passed")
        
    except Exception as e:
        logger.error(f"❌ Home Assistant connectivity test failed: {e}")
        logger.error("   Please check your configuration and try again.")
        sys.exit(1)

# For production:
app = create_app()
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8099)
