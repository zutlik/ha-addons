#!/usr/bin/env python3
"""
Main entry point for the Home Assistant Script Publisher add-on.
"""

import uvicorn
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to run the FastAPI application."""
    try:
        # Import the app after logging is configured
        from app import app
        
        # Get configuration from environment variables
        host = os.environ.get('HOST', '0.0.0.0')
        port = int(os.environ.get('PORT', '8000'))
        
        logger.info(f"Starting Home Assistant Script Publisher on {host}:{port}")
        
        # Run the FastAPI application
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

if __name__ == "__main__":
    main() 