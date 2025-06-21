# Services package
from .ha_client import HomeAssistantClient
from .ngrok_manager import NgrokManager
import logging

logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages service instances and provides access to them."""
    
    def __init__(self):
        self._ha_client = None
        self._ngrok_manager = None
        self._initialized = False
    
    def initialize_services(self):
        """Initialize all services. This can be called multiple times safely."""
        if self._initialized:
            return
        
        try:
            # Initialize Home Assistant client
            self._ha_client = HomeAssistantClient()
            logger.info("✅ Home Assistant client initialized")
            
            # Initialize Ngrok manager (this might fail if token is not configured)
            try:
                self._ngrok_manager = NgrokManager()
                logger.info("✅ Ngrok manager initialized")
            except Exception as e:
                logger.warning(f"⚠️  Ngrok manager initialization failed: {e}")
                logger.warning("   Ngrok functionality will be disabled")
                self._ngrok_manager = None
            
            self._initialized = True
            logger.info("✅ Service manager initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Service manager initialization failed: {e}")
            raise
    
    @property
    def ha_client(self) -> HomeAssistantClient:
        """Get the Home Assistant client instance."""
        if not self._initialized:
            self.initialize_services()
        return self._ha_client
    
    @property
    def ngrok_manager(self) -> NgrokManager:
        """Get the Ngrok manager instance."""
        if not self._initialized:
            self.initialize_services()
        return self._ngrok_manager
    
    def is_initialized(self) -> bool:
        """Check if services are initialized."""
        return self._initialized
    
    def get_status(self) -> dict:
        """Get the status of all services. Initializes services if needed."""
        # Initialize services if not already done
        if not self._initialized:
            try:
                self.initialize_services()
            except Exception as e:
                logger.error(f"Failed to initialize services for status check: {e}")
                return {
                    "initialized": False,
                    "ha_configured": False,
                    "ha_connected": False,
                    "ngrok_configured": False,
                    "error": str(e)
                }
        
        ha_configured = self._ha_client.is_configured() if self._ha_client else False
        ha_connected = self._ha_client.test_connection() if ha_configured else False
        ngrok_configured = self._ngrok_manager.is_configured() if self._ngrok_manager else False
        
        return {
            "initialized": True,
            "ha_configured": ha_configured,
            "ha_connected": ha_connected,
            "ngrok_configured": ngrok_configured
        }

# Global service manager instance
service_manager = ServiceManager()

# Convenience functions for backward compatibility
def get_ha_client() -> HomeAssistantClient:
    """Get the Home Assistant client instance."""
    return service_manager.ha_client

def get_ngrok_manager() -> NgrokManager:
    """Get the Ngrok manager instance."""
    return service_manager.ngrok_manager

def get_service_manager() -> ServiceManager:
    """Get the service manager instance."""
    return service_manager
