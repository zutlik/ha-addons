# When built by HA Supervisor, BUILD_FROM is injected automatically from build.yaml.
# For local development/testing, defaults to plain debian:bookworm.
ARG BUILD_FROM=debian:bookworm-slim
FROM ${BUILD_FROM}

ARG BUILD_ARCH=amd64

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    jq \
    ca-certificates \
    procps \
    unzip \
    git \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Bun (required for --channels plugin)
# Bun supports both x86_64 and aarch64 Linux
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Install ttyd (web terminal) - architecture-aware
# BUILD_ARCH from HA is: amd64, aarch64, armv7, armhf
RUN case "${BUILD_ARCH}" in \
      amd64)   TTYD_ARCH="x86_64" ;; \
      aarch64) TTYD_ARCH="aarch64" ;; \
      armv7)   TTYD_ARCH="armhf" ;; \
      armhf)   TTYD_ARCH="armhf" ;; \
      *)       TTYD_ARCH="x86_64" ;; \
    esac && \
    curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.${TTYD_ARCH}" \
      -o /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

# Copy entrypoint
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
