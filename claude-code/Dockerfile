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
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Bun (required for --channels plugin)
# Bun supports both x86_64 and aarch64 Linux
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Create non-root user for running claude.
# --dangerously-skip-permissions refuses to run as root, so all claude
# invocations must use this user. Bun lives in /root/.bun, so we open
# its permissions so the claude user can execute it.
# passwordless sudo lets claude escalate when needed (e.g. system tasks).
RUN apt-get update && apt-get install -y sudo && rm -rf /var/lib/apt/lists/* && \
    useradd -m -u 1000 -s /bin/bash claude && \
    echo "claude ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/claude && \
    chmod 0440 /etc/sudoers.d/claude && \
    chmod 755 /root && \
    chmod -R a+rX /root/.bun

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

# Copy entrypoint and the ttyd shell wrapper
COPY run.sh /run.sh
COPY claude-shell.sh /usr/local/bin/claude-shell
COPY claude-attach.sh /usr/local/bin/claude-attach
RUN chmod +x /run.sh /usr/local/bin/claude-shell /usr/local/bin/claude-attach

# Seed files for the workspace (CLAUDE.md, MEMORY.md, protocols, etc.).
# Copied into $WORK_DIR at startup only if the target file does not already
# exist, so user-edited versions are never clobbered on addon restart/upgrade.
COPY base-files/ /opt/claude-base-files/

CMD ["/run.sh"]
