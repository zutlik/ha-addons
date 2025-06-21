# app/ngrok_manager.py
import os
import subprocess
import time
import requests
import logging

# Set up logging
logger = logging.getLogger(__name__)

class NgrokManager:
    def __init__(self):
        self.ngrok_token = os.environ.get('NGROK_AUTH_TOKEN')
        self.active_tunnels = {}  # Store active tunnels by script_id
        self.ngrok_process = None
        
        # Validate ngrok token
        if not self.ngrok_token:
            logger.error("NGROK_AUTH_TOKEN environment variable is not set!")
            logger.error("Please configure the add-on with a valid ngrok authentication token.")
        else:
            logger.info(f"ngrok Token (first 5 chars): {self.ngrok_token[:5]}...")
        
        logger.info(f"ngrok Token configured: {bool(self.ngrok_token)}")

    def start_tunnel_subprocess(self, port, token=None):
        """
        Start ngrok tunnel using subprocess (command line).
        This is more reliable than the Python SDK.
        """
        try:
            # Kill any existing ngrok processes
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
                if self.ngrok_process.poll() is None:
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
            if self.ngrok_process:
                self.ngrok_process.terminate()
                self.ngrok_process = None
            raise e

    def stop_tunnel(self):
        """
        Stop the active ngrok tunnel.
        """
        try:
            if self.ngrok_process:
                self.ngrok_process.terminate()
                self.ngrok_process.wait(timeout=5)
                self.ngrok_process = None
            
            # Also kill any ngrok processes
            subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
            
            return True
        except Exception as e:
            logger.error(f"Failed to stop ngrok tunnel: {e}")
            return False

    def generate_complete_url(self, tunnel_url: str, script_id: str) -> str:
        """
        Generate the complete URL that directly executes a script.
        """
        return f"{tunnel_url}/run_script/{script_id}"

    def get_active_tunnels(self):
        """Get all active tunnels"""
        return self.active_tunnels
    
    def get_tunnel_by_script_id(self, script_id: str):
        """Get tunnel information for a specific script"""
        return self.active_tunnels.get(script_id)
    
    def add_tunnel(self, script_id: str, tunnel_info: dict):
        """Add a tunnel to active tunnels with complete_url"""
        # Generate complete_url if not present
        if 'complete_url' not in tunnel_info and 'tunnel_url' in tunnel_info:
            tunnel_info['complete_url'] = self.generate_complete_url(
                tunnel_info['tunnel_url'], 
                script_id
            )
        self.active_tunnels[script_id] = tunnel_info
    
    def remove_tunnel(self, script_id: str):
        """Remove a tunnel from active tunnels"""
        if script_id in self.active_tunnels:
            del self.active_tunnels[script_id]
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