# Installation & Setup

MC-Bot is designed to be easily deployable on most Linux environments using Docker and a universal shell script.

## 📋 Requirements
- **OS**: Linux (Ubuntu, Debian, CentOS, Arch, Alpine, etc.)
- **Architecture**: `amd64` or `arm64` (Raspberry Pi supported)
- **Dependencies**: `docker`, `docker-compose`, `curl`, `git`
- **Resources**: 
    - RAM: 2GB+ (depending on Minecraft world size)
    - Disk: 5GB+ (for backups and Docker images)

## 🚀 Quick Start (Automated)

1.  **Clone the Repo**:
    ```bash
    git clone https://github.com/your-repo/mc-bot.git
    cd mc-bot
    ```

2.  **Run the Installer**:
    ```bash
    chmod +x install/install.sh
    ./install/install.sh
    ```
    The installer will:
    - Auto-detect your OS and install missing dependencies (`apt`, `dnf`, `pacman`, or `apk`).
    - Guide you through setting your Discord Bot Token.
    - Setup your initial server configuration.

3.  **Start the Container**:
    ```bash
    make up
    ```

## 🌐 Networking & Tunneling

MC-Bot integrates **Playit.gg** for automated tunneling, allowing your server to be public without port forwarding.

- **Playit v1.0.10**: Standardized version used across the project.
- **Legacy API**: The bot uses the `https://api.playit.gg/tunnels/create` (Legacy) endpoint for reliable programmatic tunnel creation.
- **Auto-IP**: Once a tunnel is created, the bot automatically captures the public IP and stores it in `bot_config.json`.

## ⚠️ Restricted Environments (School/Work Servers)
In environments where you do not have sudo or a package manager (e.g., restricted school servers), the automated installer may fail to install `docker` or `tmux`.

**Manual Workaround**:
1. Ensure `docker` is already provided by the administrator.
2. If `tmux` is missing, use the `server_mock.py` or ensure the environment provides a terminal multiplexer.
3. Use `pip install -r requirements.txt --user` if global installation is blocked.

## 🛠️ Makefile Commands
- `make build`: Build the Docker image.
- `make up`: Start the bot (detached).
- `make down`: Stop the bot.
- `make logs`: View live bot and server logs.
- `make test`: Run the full test suite in a clean container.
