# Minecraft Discord Bot Dockerfile
# Python 3.11 + Java 21 + tmux + Playit

FROM python:3.11-slim

LABEL maintainer="Marjan Ceh"
LABEL description="Minecraft Discord Bot with Java 21 and Playit.gg"

# Create directory for man pages (required for openjdk in slim images)
RUN mkdir -p /usr/share/man/man1

# Install Java 21, tmux, curl and jq
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    tmux \
    curl \
    jq \
    ca-certificates \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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

# Add non-root user for security
RUN groupadd -r bot && useradd -r -g bot -d /app bot

# Install Python dependencies first — layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create runtime directories and set permissions before copying source
RUN mkdir -p /app/mc-server /app/backups /app/logs /app/data \
    && chown -R bot:bot /app

# Copy bot source — only these layers rebuild on code changes
COPY --chown=bot:bot bot.py .
COPY --chown=bot:bot cogs/ ./cogs/
COPY --chown=bot:bot src/ ./src/

# Switch to non-root user
USER bot

EXPOSE 25565

CMD ["python", "bot.py"]
