#!/bin/bash
# This script is the entrypoint for the Docker container.
# It sets up environment variables and starts the Python FastAPI application.

echo "Starting Shell Command Executor Add-on with FastAPI..."

# Home Assistant Supervisor usually provides options.json in /data/
# Use jq to parse the JSON and extract the token.
# If jq is not available in the base image, you might need to add it to the Dockerfile
# (e.g., RUN apt-get update && apt-get install -y jq)
export HOME_ASSISTANT_TOKEN=$(jq --raw-output '.HOME_ASSISTANT_TOKEN' /data/options.json)

# Start the FastAPI application using Uvicorn
# The app is located at /app/app.py (module app, FastAPI instance 'app')
# It will listen on 0.0.0.0:8099 as defined in config.json ports and Dockerfile EXPOSE
uvicorn app.app:app --host 0.0.0.0 --port 8099 --log-level info
