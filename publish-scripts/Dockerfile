# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements files
COPY app/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Web UI builder stage
FROM node:18-alpine as web-builder

# Set working directory for web build
WORKDIR /web

# Copy web UI source
COPY web/package*.json ./
COPY web/ ./

# Install dependencies and build
RUN npm ci && npm run build

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    wget \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Copy the application code
COPY app/ .

# Copy the built web UI from web-builder stage
COPY --from=web-builder /web/dist ./static

# Copy the run script
COPY run.sh /usr/bin/run.sh
RUN chmod +x /usr/bin/run.sh

# Set the PATH to include the user's local bin directory
ENV PATH=/root/.local/bin:$PATH

# Expose the port the app runs on
EXPOSE 8099

# Run the application
CMD ["/usr/bin/run.sh"]
