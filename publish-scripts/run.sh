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

# Check if NGROK_AUTH_TOKEN is already set as an environment variable
# If not, try to get it from Home Assistant Supervisor options.json
if [ -z "$NGROK_AUTH_TOKEN" ]; then
    export NGROK_AUTH_TOKEN=$(jq --raw-output '.NGROK_AUTH_TOKEN' /data/options.json)
    echo "Using ngrok auth token from /data/options.json"
else
    echo "Using NGROK_AUTH_TOKEN from environment variable"
fi

# Check if HA_BASE_URL is already set as an environment variable
# If not, try to get it from Home Assistant Supervisor options.json
if [ -z "$HA_BASE_URL" ]; then
    # Try to read HA_BASE_URL from options.json, but continue if it fails
    if [ -f "/data/options.json" ] && jq -e '.HA_BASE_URL' /data/options.json > /dev/null 2>&1; then
        export HA_BASE_URL=$(jq --raw-output '.HA_BASE_URL' /data/options.json)
        echo "Using HA_BASE_URL from /data/options.json"
    else
        echo "No HA_BASE_URL found in /data/options.json, continuing without it"
    fi
else
    echo "Using HA_BASE_URL from environment variable"
fi

# Check if PORT is already set as an environment variable
# If not, try to get it from Home Assistant Supervisor options.json
if [ -z "$PORT" ]; then
    # Try to read PORT from options.json, but continue if it fails
    if [ -f "/data/options.json" ] && jq -e '.PORT' /data/options.json > /dev/null 2>&1; then
        export PORT=$(jq --raw-output '.PORT' /data/options.json)
        echo "Using PORT from /data/options.json: $PORT"
    else
        echo "No PORT found in /data/options.json, using default: 8099"
        export PORT=8099
    fi
else
    echo "Using PORT from environment variable: $PORT"
fi

# Set the app directory as the base for Python imports
export PYTHONPATH="/app:${PYTHONPATH:-}"

# Change to the app directory to ensure all imports work correctly
cd /app

# Start the FastAPI application using Gunicorn with a single Uvicorn worker
# The app is located at /app/main.py (module main, FastAPI instance 'app')
# It will listen on 0.0.0.0:$PORT as defined in config.json ports and Dockerfile EXPOSE
gunicorn main:app --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker --workers 1 --log-level info
