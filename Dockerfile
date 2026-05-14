# Minecraft Discord Bot Dockerfile
# Python 3.11 + Java 21 + tmux + Playit

FROM python:3.11-slim

# Install Java 21, tmux, and Playit
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    tmux \
    curl \
    gnupg \
    && curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor > /etc/apt/trusted.gpg.d/playit.gpg \
    && echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./" > /etc/apt/sources.list.d/playit-cloud.list \
    && apt-get update \
    && apt-get install -y playit \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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
