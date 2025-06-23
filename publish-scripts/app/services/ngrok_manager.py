import subprocess
import time
import requests
import logging
import asyncio
from datetime import datetime, timedelta
from settings import get_settings
import secrets
from typing import Optional

# Set up logging
logger = logging.getLogger(__name__)

class NgrokManager:
    def __init__(self):
        settings = get_settings()
        self.ngrok_token = settings.ngrok_auth_token
        self.active_tunnels = {}  # Store active tunnels by script_id
        self.hash_to_script = {}  # Map unique hash to script_id
        self.ngrok_process = None
        self.cleanup_task = None # To hold the cleanup task
        self._warmed_up = False  # Track if ngrok has been warmed up
        
        # Log ngrok token status (don't raise exception for missing token)
        if not self.ngrok_token:
            logger.warning("⚠️  NGROK_AUTH_TOKEN environment variable is not set!")
            logger.warning("   Ngrok functionality will be disabled.")
            logger.warning("   To enable ngrok tunnels, add NGROK_AUTH_TOKEN to configuration.")
        else:
            logger.info(f"✅ ngrok Token (first 5 chars): {self.ngrok_token[:5]}...")
        
        logger.info(f"ngrok Token configured: {bool(self.ngrok_token)}")
        # Don't start cleanup task automatically - only when needed

    def warm_up_ngrok(self, port):
        """
        Pre-initialize ngrok to avoid first-time startup delays.
        This starts ngrok in the background and waits for it to be ready.
        """
        if self._warmed_up or not self.ngrok_token:
            return True
            
        try:
            logger.info("🔥 Warming up ngrok for faster first tunnel creation...")
            
            # Start ngrok in background
            cmd = ['ngrok', 'http', str(port), '--log=stdout']
            if self.ngrok_token:
                cmd.extend(['--authtoken', self.ngrok_token])
            
            self.ngrok_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for ngrok to be ready with retry logic
            max_retries = 8
            retry_delay = 1
            
            for attempt in range(max_retries):
                logger.info(f"Warming up ngrok (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                
                # Check if process is still running
                if self.ngrok_process.poll() is not None:
                    stderr_output = ""
                    if self.ngrok_process.stderr:
                        stderr_output = self.ngrok_process.stderr.read()
                    logger.error(f"ngrok warm-up failed. stderr: {stderr_output}")
                    return False
                
                # Try to get the URL to confirm ngrok is ready
                url = self.get_existing_tunnel_url()
                if url:
                    logger.info(f"✅ ngrok warmed up successfully: {url}")
                    self._warmed_up = True
                    return True
                
                # Increase delay for next attempt
                retry_delay = min(retry_delay * 1.2, 4)
                
                if attempt < max_retries - 1:
                    logger.info(f"ngrok not ready yet, retrying in {retry_delay:.1f} seconds...")
            
            # If warm-up fails, clean up and return False
            logger.warning("❌ ngrok warm-up failed after all attempts")
            if self.ngrok_process:
                self.ngrok_process.terminate()
                self.ngrok_process = None
            return False
            
        except Exception as e:
            logger.error(f"Error during ngrok warm-up: {e}")
            if self.ngrok_process:
                self.ngrok_process.terminate()
                self.ngrok_process = None
            return False

    def start_cleanup_task(self):
        """Start the background task to clean up expired tunnels."""
        # Only start if there are tunnels with expiration times
        has_expiring_tunnels = any(
            'expiration_time' in tunnel_info 
            for tunnel_info in self.active_tunnels.values()
        )
        
        if has_expiring_tunnels and (self.cleanup_task is None or self.cleanup_task.done()):
            try:
                self.cleanup_task = asyncio.create_task(self._cleanup_expired_tunnels())
                logger.info("🔥 Tunnel cleanup task started.")
            except Exception as e:
                logger.error(f"Failed to start cleanup task: {e}")

    async def _cleanup_expired_tunnels(self):
        """Periodically check for and remove expired tunnels."""
        try:
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
                        break  # Exit the loop since no more tunnels
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled.")
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

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
            
        # If ngrok was warmed up, try to use the existing process
        if self._warmed_up and self.ngrok_process and self.ngrok_process.poll() is None:
            url = self.get_existing_tunnel_url()
            if url:
                logger.info("✅ Using warmed-up ngrok process")
                return url
            else:
                logger.warning("Warmed-up ngrok process not responding, will restart")
                self._warmed_up = False
            
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
            
            # Wait for ngrok to start and get the URL with retry logic
            max_retries = 5
            retry_delay = 2  # Start with 2 seconds
            
            for attempt in range(max_retries):
                logger.info(f"Waiting for ngrok to start (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_delay)
                
                # Check if process is still running
                if self.ngrok_process.poll() is not None:
                    # Process died, check stderr for error
                    stderr_output = ""
                    if self.ngrok_process.stderr:
                        stderr_output = self.ngrok_process.stderr.read()
                    logger.error(f"ngrok process died. stderr: {stderr_output}")
                    raise Exception("ngrok process failed to start")
                
                # Try to get the URL
                url = self.get_existing_tunnel_url()
                if url:
                    logger.info(f"✅ ngrok tunnel started successfully: {url}")
                    return url
                
                # Increase delay for next attempt (exponential backoff)
                retry_delay = min(retry_delay * 1.5, 8)  # Cap at 8 seconds
                
                if attempt < max_retries - 1:
                    logger.info(f"ngrok API not ready yet, retrying in {retry_delay:.1f} seconds...")
            
            # If we get here, all retries failed
            stderr_output = ""
            if self.ngrok_process.stderr:
                stderr_output = self.ngrok_process.stderr.read()
            logger.error(f"Failed to get tunnel URL after {max_retries} attempts. stderr: {stderr_output}")
            raise Exception(f"Failed to get tunnel URL after {max_retries} attempts. ngrok may not have started properly.")
                
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
    
    def generate_unique_hash(self, length=12):
        """Generate a unique hash for the dynamic endpoint."""
        while True:
            hash_str = secrets.token_urlsafe(length)[:length]
            if hash_str not in self.hash_to_script:
                return hash_str

    def add_tunnel(self, script_id: str, tunnel_info: dict, timeout_minutes: Optional[int] = None):
        """Add a tunnel to active tunnels with complete_url and optional expiration."""
        # Generate a unique hash for this tunnel
        if 'unique_hash' not in tunnel_info:
            unique_hash = self.generate_unique_hash()
            tunnel_info['unique_hash'] = unique_hash
        else:
            unique_hash = tunnel_info['unique_hash']
        self.hash_to_script[unique_hash] = script_id

        # Generate complete_url if not present
        if 'complete_url' not in tunnel_info and 'tunnel_url' in tunnel_info:
            tunnel_info['complete_url'] = f"{tunnel_info['tunnel_url']}/run/{unique_hash}"
        if timeout_minutes:
            tunnel_info['expiration_time'] = datetime.utcnow() + timedelta(minutes=timeout_minutes)
            logger.info(f"Tunnel for {script_id} will expire at {tunnel_info['expiration_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self.active_tunnels[script_id] = tunnel_info
        
        # Start cleanup task if this tunnel has an expiration time
        if timeout_minutes:
            self.start_cleanup_task()

    def get_script_id_by_hash(self, unique_hash: str):
        """Get the script_id associated with a unique hash."""
        return self.hash_to_script.get(unique_hash)

    def remove_tunnel(self, script_id: str):
        """Remove a tunnel from active tunnels and hash mapping."""
        tunnel_info = self.active_tunnels.get(script_id)
        if tunnel_info and 'unique_hash' in tunnel_info:
            unique_hash = tunnel_info['unique_hash']
            if unique_hash in self.hash_to_script:
                del self.hash_to_script[unique_hash]
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