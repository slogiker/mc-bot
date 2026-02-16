# Minecraft Discord Bot Dockerfile
# Python 3.11 + Java 21 + tmux

FROM python:3.11-slim

# Build arguments for cache busting
ARG CACHEBUST=1

# Install Java 21, tmux, and other dependencies
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    tmux \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Use build argument to invalidate cache if needed
RUN echo "Cache buster: $CACHEBUST"

# Copy bot files
COPY bot.py .
COPY cogs/ ./cogs/
COPY src/ ./src/
COPY data/ ./data/

# Create necessary directories
RUN mkdir -p /app/mc-server /app/backups /app/logs

# Expose only Minecraft port
# RCON (25575) should NOT be exposed - only accessible within container network
EXPOSE 25565

# Run the bot
CMD ["python", "bot.py"]
