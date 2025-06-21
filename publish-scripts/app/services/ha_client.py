import os
import requests
import logging
from typing import Optional, List, Dict, Any
from settings import get_settings

# Set up logging
logger = logging.getLogger(__name__)

class HomeAssistantClient:
    def __init__(self):
        settings = get_settings()
        self.ha_token = os.getenv("HASSIO_TOKEN", default=settings.hassio_token)
        self.ha_base_url = settings.ha_base_url
        
        # Validate that the token is available
        if not self.ha_token:
            logger.error("HASSIO_TOKEN environment variable is not set!")
            logger.error("Please configure the add-on with a valid Home Assistant token.")
        else:
            logger.info(f"Home Assistant Token (first 5 chars): {self.ha_token[:5]}...")
        
        logger.info(f"Home Assistant Base URL: {self.ha_base_url}")

    def test_connection(self) -> bool:
        """
        Test connectivity to Home Assistant.
        """
        if not self.ha_token:
            logger.error("Cannot test connection: Home Assistant token not configured")
            return False
        
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.ha_base_url}/"
        logger.info(f"Testing Home Assistant connectivity: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info("✅ Home Assistant connectivity test successful")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Home Assistant connectivity test failed: {e}")
            return False

    def call_api(self, service: str, data: Optional[dict] = None) -> dict:
        """
        Make a call to the Home Assistant API to execute services.
        """
        if not self.ha_token:
            raise Exception("Home Assistant token not configured")
        
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        
        payload = data or {}
        
        url = f"{self.ha_base_url}/services/{service}"
        logger.info(f"Calling Home Assistant API: {url}")
        logger.info(f"Payload: {payload}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Home Assistant API call failed: {e}")
            raise Exception(f"Failed to call Home Assistant API: {e}")

    def get_api(self, endpoint: str) -> dict:
        """
        Make a GET call to the Home Assistant API.
        """
        if not self.ha_token:
            raise Exception("Home Assistant token not configured")
        
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.ha_base_url}/{endpoint}"
        logger.info(f"Calling Home Assistant API: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Home Assistant API call failed: {e}")
            raise Exception(f"Failed to call Home Assistant API: {e}")

    def run_script(self, script_id: str) -> dict:
        """
        Execute a Home Assistant script by its entity ID.
        """
        logger.info(f"Executing Home Assistant script: {script_id}")
        
        # Call the script.turn_on service with the script entity ID
        payload = {"entity_id": script_id}
        return self.call_api("script/turn_on", payload)

    async def run_script_async(self, script_id: str) -> dict:
        """
        Execute a Home Assistant script by its entity ID (async version).
        """
        return self.run_script(script_id)

    def script_exists(self, script_id: str) -> bool:
        """
        Check if a script exists in Home Assistant.
        """
        try:
            # Get the script state
            response = self.get_api(f"states/{script_id}")
            return response.get('state') is not None
        except Exception as e:
            logger.error(f"Error checking if script {script_id} exists: {e}")
            return False

    async def script_exists_async(self, script_id: str) -> bool:
        """
        Check if a script exists in Home Assistant (async version).
        """
        return self.script_exists(script_id)

    def get_scripts(self) -> List[Dict[str, Any]]:
        """
        Get all available scripts from Home Assistant.
        """
        try:
            # Get all states and filter for scripts
            states = self.get_api("states")
            scripts = []
            
            for state in states:
                if state.get('entity_id', '').startswith('script.'):
                    scripts.append({
                        'entity_id': state['entity_id'],
                        'name': state.get('attributes', {}).get('friendly_name', state['entity_id']),
                        'state': state.get('state'),
                        'attributes': state.get('attributes', {})
                    })
            
            return scripts
        except Exception as e:
            logger.error(f"Error getting scripts: {e}")
            return []

    async def get_scripts_async(self) -> List[Dict[str, Any]]:
        """
        Get all available scripts from Home Assistant (async version).
        """
        return self.get_scripts()

    def get_script(self, script_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific script.
        """
        try:
            # Get the script state
            response = self.get_api(f"states/{script_id}")
            
            if response.get('state') is not None:
                return {
                    'entity_id': response['entity_id'],
                    'name': response.get('attributes', {}).get('friendly_name', response['entity_id']),
                    'state': response.get('state'),
                    'attributes': response.get('attributes', {})
                }
            return None
        except Exception as e:
            logger.error(f"Error getting script {script_id}: {e}")
            return None

    async def get_script_async(self, script_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific script (async version).
        """
        return self.get_script(script_id)

    def is_configured(self) -> bool:
        """
        Check if the Home Assistant client is properly configured.
        """
        return bool(self.ha_token)

    def get_base_url(self) -> str:
        """
        Get the Home Assistant base URL.
        """
        return self.ha_base_url 