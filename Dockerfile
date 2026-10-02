# Minecraft Discord Bot Dockerfile
# Python 3.11 + Java 21 + tmux + Playit

FROM python:3.11-slim

# Default Java version (e.g., 8, 11, 17, 21, 25). Can be overridden via --build-arg JAVA_VERSION=...
ARG JAVA_VERSION=21

LABEL maintainer="Marjan Ceh"
LABEL description="Minecraft Discord Bot with customizable Java and Playit.gg"

# Create directory for man pages and apt keyrings
RUN mkdir -p /usr/share/man/man1 /etc/apt/keyrings

# Install core utilities, Eclipse Adoptium repository, NAS backup tools, and specified Java version
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    tmux \
    ca-certificates \
    procps \
    gnupg \
    wget \
    tar \
    gzip \
    zstd \
    rsync \
    openssh-client \
    && wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor -o /etc/apt/keyrings/adoptium.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb bookworm main" > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update \
    && (apt-get install -y --no-install-recommends temurin-${JAVA_VERSION}-jre || apt-get install -y --no-install-recommends openjdk-${JAVA_VERSION}-jre-headless) \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV DEFAULT_JAVA_VERSION=${JAVA_VERSION}

# Install Playit.gg binaries with architecture auto-detection
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
        x86_64)  PLAYIT_ARCH="amd64" ;; \
        aarch64) PLAYIT_ARCH="aarch64" ;; \
        armv7l)  PLAYIT_ARCH="armv7" ;; \
        *)       PLAYIT_ARCH="amd64" ;; \
    esac && \
    echo "Detected architecture: $ARCH, using Playit arch: $PLAYIT_ARCH" && \
    curl -Lo /usr/local/bin/playit "https://github.com/playit-cloud/playit-agent/releases/download/v1.0.10/playit-linux-$PLAYIT_ARCH" && \
    curl -Lo /usr/local/bin/playit-cli "https://github.com/playit-cloud/playit-agent/releases/download/v1.0.10/playit-cli-linux-$PLAYIT_ARCH" && \
    chmod +x /usr/local/bin/playit /usr/local/bin/playit-cli

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Add non-root user for security
RUN groupadd -r bot && useradd -r -g bot -d /app bot

# Install Python dependencies first - layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create runtime directories and set permissions before copying source
RUN mkdir -p /app/mc-server /app/backups /app/logs /app/data /app/data/jre \
    && chown -R bot:bot /app

# Copy bot source - only these layers rebuild on code changes
COPY --chown=bot:bot bot.py .
COPY --chown=bot:bot cogs/ ./cogs/
COPY --chown=bot:bot src/ ./src/

# Switch to non-root user
USER bot

EXPOSE 25565
EXPOSE 24454/udp

CMD ["python", "bot.py"]
