# Minecraft Discord Bot Dockerfile
# Python 3.11 + Java 21 + tmux + Playit

FROM python:3.11-slim

# Install Java 21, tmux, and Playit
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    tmux \
    git \
    curl \
    gnupg \
    && curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor > /etc/apt/trusted.gpg.d/playit.gpg \
    && echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./" > /etc/apt/sources.list.d/playit-cloud.list \
    && apt-get update \
    && apt-get install -y playit \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first — layer is cached unless requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create runtime directories before copying source so this layer is stable
RUN mkdir -p /app/mc-server /app/backups /app/logs

# Copy bot source — only these layers rebuild on code changes
COPY bot.py .
COPY cogs/ ./cogs/
COPY src/ ./src/
COPY data/ ./data/

EXPOSE 25565

CMD ["python", "bot.py"]
