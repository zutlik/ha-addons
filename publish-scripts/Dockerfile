# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
FROM python:3.11-slim as builder

# Install build dependencies with extra packages for i386
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    jq \
    && if [ "$TARGETARCH" = "i386" ]; then \
        apt-get install -y --no-install-recommends \
        python3-dev \
        libffi-dev \
        libssl-dev \
        libjpeg-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        wget \
        ca-certificates \
        pkg-config; \
    fi \
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
        pip install --no-cache-dir --user -r requirements-i386.txt || \
        (echo "Some packages failed to install, continuing with available packages" && \
         pip install --no-cache-dir --user fastapi==0.88.0 uvicorn==0.20.0 requests==2.28.1 gunicorn==20.1.0); \
    else \
        echo "Using standard requirements" && \
        pip install --no-cache-dir --user -r requirements.txt; \
    fi

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install ngrok binary for all architectures (as fallback for Python package issues)
ARG TARGETARCH
RUN case "$TARGETARCH" in \
        amd64) \
            echo "Installing ngrok binary for amd64" && \
            wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz && \
            tar -xzf ngrok-v3-stable-linux-amd64.tgz && \
            mv ngrok /usr/local/bin/ && \
            rm ngrok-v3-stable-linux-amd64.tgz \
            ;; \
        arm64) \
            echo "Installing ngrok binary for arm64" && \
            wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz && \
            tar -xzf ngrok-v3-stable-linux-arm64.tgz && \
            mv ngrok /usr/local/bin/ && \
            rm ngrok-v3-stable-linux-arm64.tgz \
            ;; \
        arm) \
            echo "Installing ngrok binary for arm" && \
            wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm.tgz && \
            tar -xzf ngrok-v3-stable-linux-arm.tgz && \
            mv ngrok /usr/local/bin/ && \
            rm ngrok-v3-stable-linux-arm.tgz \
            ;; \
        i386) \
            echo "Installing ngrok binary for i386" && \
            wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-386.tgz && \
            tar -xzf ngrok-v3-stable-linux-386.tgz && \
            mv ngrok /usr/local/bin/ && \
            rm ngrok-v3-stable-linux-386.tgz \
            ;; \
        *) \
            echo "Unsupported architecture: $TARGETARCH" && \
            exit 1 \
            ;; \
    esac

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
