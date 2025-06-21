#!/bin/bash
# This script is the entrypoint for the Docker container.
# It sets up environment variables and starts the Python FastAPI application.

echo "Starting Shell Command Executor Add-on with FastAPI..."

# Load environment variables from .env file if it exists (for local development)
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if HOME_ASSISTANT_TOKEN is already set as an environment variable
# If not, try to get it from Home Assistant Supervisor options.json
if [ -z "$HOME_ASSISTANT_TOKEN" ]; then
    # Home Assistant Supervisor usually provides options.json in /data/
    # Use jq to parse the JSON and extract the token.
    # If jq is not available in the base image, you might need to add it to the Dockerfile
    # (e.g., RUN apt-get update && apt-get install -y jq)
    export HOME_ASSISTANT_TOKEN=$(jq --raw-output '.HOME_ASSISTANT_TOKEN' /data/options.json)
    echo "Using Home Assistant token from /data/options.json"
    echo "HOME_ASSISTANT_TOKEN: ${HOME_ASSISTANT_TOKEN:0:10}..."
else
    echo "Using HOME_ASSISTANT_TOKEN from environment variable"
fi

# Start the FastAPI application using Gunicorn with a single Uvicorn worker
# The app is located at /app/app.py (module app, FastAPI instance 'app')
# It will listen on 0.0.0.0:8099 as defined in config.json ports and Dockerfile EXPOSE
gunicorn app:app --bind 0.0.0.0:8099 --worker-class uvicorn.workers.UvicornWorker --workers 1 --log-level info
