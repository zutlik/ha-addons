# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
FROM python:3.13.3-slim as builder

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
COPY app/requirements-i386.txt .

# Install Python dependencies based on architecture
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "i386" ]; then \
        echo "Using i386-specific requirements" && \
        pip install --no-cache-dir --user -r requirements-i386.txt; \
    else \
        echo "Using standard requirements" && \
        pip install --no-cache-dir --user -r requirements.txt; \
    fi

# Final stage
FROM python:3.13.3-slim

# Install runtime dependencies and ngrok
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install ngrok binary for non-i386 architectures (i386 uses Python package)
ARG TARGETARCH
RUN if [ "$TARGETARCH" != "i386" ]; then \
        case "$TARGETARCH" in \
            amd64) ARCH=amd64 ;; \
            arm64) ARCH=arm64 ;; \
            arm) ARCH=arm ;; \
            *) echo "Unsupported architecture: $TARGETARCH" && exit 1 ;; \
        esac \
        && wget -q "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-${ARCH}.tgz" \
        && tar -xzf "ngrok-v3-stable-linux-${ARCH}.tgz" \
        && mv ngrok /usr/local/bin/ \
        && rm "ngrok-v3-stable-linux-${ARCH}.tgz"; \
    else \
        echo "Skipping ngrok binary installation for i386 (using Python package)"; \
    fi

# Set the working directory in the container
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /root/.local

# Copy your application files (app.py and templates)
COPY app/ .

# Copy the run script and make it executable
COPY run.sh /usr/bin/run.sh
RUN chmod +x /usr/bin/run.sh

# Add local bin to PATH
ENV PATH=/root/.local/bin:$PATH

# Expose the port that FastAPI/Uvicorn will listen on (matching config.json)
EXPOSE 8099

# Command to run the add-on when the container starts
CMD ["/usr/bin/run.sh"]
