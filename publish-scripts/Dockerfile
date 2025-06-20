# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
FROM python:3.13.3-slim

# Install system dependencies including jq for parsing JSON
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application files (app.py and templates)
COPY app/ .

# Copy the run script and make it executable
COPY run.sh /usr/bin/run.sh
RUN chmod +x /usr/bin/run.sh

# Expose the port that FastAPI/Uvicorn will listen on (matching config.json)
EXPOSE 8099

# Command to run the add-on when the container starts
CMD ["/usr/bin/run.sh"]
