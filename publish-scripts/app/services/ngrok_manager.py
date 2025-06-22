import subprocess
import time
import requests
import logging
import asyncio
from datetime import datetime, timedelta
from settings import get_settings

# Set up logging
logger = logging.getLogger(__name__)

class NgrokManager:
    def __init__(self):
        settings = get_settings()
        self.ngrok_token = settings.ngrok_auth_token
        self.active_tunnels = {}  # Store active tunnels by script_id
        self.ngrok_process = None
        self.cleanup_task = None # To hold the cleanup task
        
        # Log ngrok token status (don't raise exception for missing token)
        if not self.ngrok_token:
            logger.warning("⚠️  NGROK_AUTH_TOKEN environment variable is not set!")
            logger.warning("   Ngrok functionality will be disabled.")
            logger.warning("   To enable ngrok tunnels, add NGROK_AUTH_TOKEN to configuration.")
        else:
            logger.info(f"✅ ngrok Token (first 5 chars): {self.ngrok_token[:5]}...")
        
        logger.info(f"ngrok Token configured: {bool(self.ngrok_token)}")
        self.start_cleanup_task()

    def start_cleanup_task(self):
        """Start the background task to clean up expired tunnels."""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_tunnels())
            logger.info("🔥 Tunnel cleanup task started.")

    async def _cleanup_expired_tunnels(self):
        """Periodically check for and remove expired tunnels."""
        while True:
            await asyncio.sleep(60) # Check every 60 seconds
            now = datetime.utcnow()
            expired_scripts = []
            
            # Using list() to avoid issues with modifying dict during iteration
            for script_id, tunnel_info in list(self.active_tunnels.items()):
                if 'expiration_time' in tunnel_info and now > tunnel_info['expiration_time']:
                    expired_scripts.append(script_id)
            
            if expired_scripts:
                logger.info(f"⌛ Found {len(expired_scripts)} expired tunnels: {', '.join(expired_scripts)}")
                for script_id in expired_scripts:
                    self.remove_tunnel(script_id)
                
                # If no tunnels are left, stop the main ngrok process
                if not self.active_tunnels:
                    logger.info("All tunnels expired or removed, stopping ngrok process.")
                    self.stop_tunnel()

    def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            logger.info("🔥 Tunnel cleanup task stopped.")

    def is_configured(self) -> bool:
        """Check if ngrok is properly configured."""
        return bool(self.ngrok_token)

    def get_existing_tunnel_url(self):
        """Check for an existing tunnel URL from the ngrok API."""
        try:
            response = requests.get('http://localhost:4040/api/tunnels', timeout=2)
            if response.status_code == 200:
                tunnels = response.json().get('tunnels', [])
                if tunnels:
                    return tunnels[0].get('public_url')
        except requests.ConnectionError:
            logger.info("Ngrok API not available. Assuming no active tunnel.")
        except Exception as e:
            logger.error(f"Error checking ngrok API: {e}")
        return None

    def start_tunnel_subprocess(self, port, token=None):
        """
        Start ngrok tunnel using subprocess (command line) if not already running.
        This is more reliable than the Python SDK.
        """
        # If process exists and is running, try to get its URL
        if self.ngrok_process and self.ngrok_process.poll() is None:
            logger.info("ngrok process is already running.")
            url = self.get_existing_tunnel_url()
            if url:
                return url
            logger.warning("ngrok process running, but couldn't get URL. Will attempt to restart.")
            
        try:
            # Kill any orphaned ngrok processes before starting a new one
            subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
            time.sleep(1)
            
            # Start ngrok tunnel
            cmd = ['ngrok', 'http', str(port), '--log=stdout']
            if token:
                cmd.extend(['--authtoken', token])
            
            self.ngrok_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for ngrok to start and get the URL
            time.sleep(3)
            url = self.get_existing_tunnel_url()
            if url:
                return url
            else:
                # If API fails, check logs or raise error
                stderr_output = ""
                if self.ngrok_process.stderr:
                    stderr_output = self.ngrok_process.stderr.read()
                logger.error(f"ngrok stderr: {stderr_output}")
                raise Exception("Failed to get tunnel URL after starting process.")
                
        except Exception as e:
            logger.error(f"Error starting ngrok tunnel: {e}")
            if self.ngrok_process:
                self.ngrok_process.terminate()
                self.ngrok_process = None
            raise

    def stop_tunnel(self):
        """
        Stop the active ngrok tunnel process.
        """
        try:
            if self.ngrok_process:
                logger.info("Terminating ngrok process...")
                self.ngrok_process.terminate()
                self.ngrok_process.wait(timeout=5)
                self.ngrok_process = None
            
            # Also kill any lingering ngrok processes just in case
            subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
            logger.info("ngrok process stopped.")
            
            return True
        except Exception as e:
            logger.error(f"Failed to stop ngrok tunnel: {e}")
            return False

    def generate_complete_url(self, tunnel_url: str, script_id: str) -> str:
        """
        Generate the complete URL that directly executes a script.
        """
        return f"{tunnel_url}/scripts/run/{script_id}"

    def get_active_tunnels(self):
        """Get all active tunnels"""
        return self.active_tunnels
    
    def get_tunnel_by_script_id(self, script_id: str):
        """Get tunnel information for a specific script"""
        return self.active_tunnels.get(script_id)
    
    def add_tunnel(self, script_id: str, tunnel_info: dict, timeout_minutes: int | None = None):
        """Add a tunnel to active tunnels with complete_url and optional expiration."""
        # Generate complete_url if not present
        if 'complete_url' not in tunnel_info and 'tunnel_url' in tunnel_info:
            tunnel_info['complete_url'] = self.generate_complete_url(
                tunnel_info['tunnel_url'], 
                script_id
            )
        
        if timeout_minutes:
            tunnel_info['expiration_time'] = datetime.utcnow() + timedelta(minutes=timeout_minutes)
            logger.info(f"Tunnel for {script_id} will expire at {tunnel_info['expiration_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}")

        self.active_tunnels[script_id] = tunnel_info
    
    def remove_tunnel(self, script_id: str):
        """Remove a tunnel from active tunnels"""
        if script_id in self.active_tunnels:
            del self.active_tunnels[script_id]
            logger.info(f"Removed tunnel for script {script_id}.")
            return True
        return False
    
    def is_tunnel_active_for_script(self, script_id: str):
        """Check if there's an active tunnel for a specific script"""
        return script_id in self.active_tunnels
    
    def get_tunnel_url_for_script(self, script_id: str):
        """Get the tunnel URL for a specific script"""
        tunnel_info = self.active_tunnels.get(script_id)
        if tunnel_info:
            return tunnel_info.get('tunnel_url')
        return None
    
    def get_complete_url_for_script(self, script_id: str):
        """Get the complete URL for a specific script"""
        tunnel_info = self.active_tunnels.get(script_id)
        if tunnel_info:
            return tunnel_info.get('complete_url')
        return None
    
    def get_tunnel_count(self):
        """Get the number of active tunnels"""
        return len(self.active_tunnels)
    
    def clear_all_tunnels(self):
        """Clear all active tunnels"""
        self.active_tunnels.clear()

    # Legacy methods for backward compatibility
    def get_tunnel_info(self):
        """
        Get information about the active tunnel (legacy method).
        Returns the first tunnel if multiple exist.
        """
        if self.active_tunnels:
            return next(iter(self.active_tunnels.values()))
        return None

    def set_tunnel_info(self, tunnel_info):
        """
        Set the active tunnel information (legacy method).
        """
        if tunnel_info and 'script_id' in tunnel_info:
            self.active_tunnels[tunnel_info['script_id']] = tunnel_info

    def is_tunnel_active(self):
        """
        Check if there's an active tunnel (legacy method).
        """
        return len(self.active_tunnels) > 0

    def get_tunnel_url(self):
        """
        Get the current tunnel URL (legacy method).
        Returns the first tunnel URL if multiple exist.
        """
        if self.active_tunnels:
            first_tunnel = next(iter(self.active_tunnels.values()))
            return first_tunnel.get('tunnel_url')
        return None 