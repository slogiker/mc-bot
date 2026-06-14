# Installation & Setup

MC-Bot is designed to be easily deployable on most Linux environments using Docker and a universal shell script. It also features a highly advanced, resumable Windows installer.

## 📋 Requirements
- **OS**: Linux (Ubuntu, Debian, CentOS, Arch, Alpine, etc.) or Windows (via WSL2).
- **Architecture**: `amd64` or `arm64` (Raspberry Pi supported).
- **Dependencies**: `docker`, `docker-compose`, `curl`, `git`.
- **Resources**: 
    - RAM: 2GB+ (depending on Minecraft world size).
    - Disk: 5GB+ (for backups and Docker images).

## 🚀 Linux / macOS / Standard WSL (Automated)

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
    The installer will auto-detect your OS and install missing dependencies, prompt for your `BOT_TOKEN`, and auto-generate a secure `RCON_PASSWORD`.

## 🪟 Windows (install.bat)

The `install/install.bat` is a sophisticated, 8-step resumable installer that automates the setup of an isolated WSL2 environment.

| Step | Operation | Details |
| :--- | :--- | :--- |
| **1** | **System Check** | Admin elevation check, Windows build verification (>=19041), and virtualization check. |
| **2** | **Docker Detection** | Detects Docker Desktop. If missing, offers to install WSL + Docker Engine. |
| **3** | **WSL Installation** | Installs WSL2 components. Sets a `RunOnce` registry key to resume after reboot. |
| **4** | **Distro Import** | Imports a minimal Ubuntu 22.04 rootfs as a dedicated `MCBot` instance. |
| **5** | **User Creation** | Creates the `mc-bot` user non-interactively and generates credentials. |
| **6** | **Engine Setup** | Runs `wsl_docker_setup.sh` inside the instance to install Docker Engine. |
| **7** | **Config Prompt** | Prompts for Discord Token and RCON password; writes the `.env` file. |
| **8** | **Launch** | Executes `docker compose up -d --build` to start the bot. |

**Resume Logic**: Every step is persisted to the Windows Registry. If a reboot is required (e.g., after Step 3), the script resumes automatically upon login.

## 🌐 Networking & Tunneling (Playit.gg)

MC-Bot integrates **Playit.gg** for automated tunneling.
- **Automated Provisioning**: The bot can programmatically create tunnels via the Playit Legacy API.
- **Version 1.0.10**: Standardized version used to ensure stability and compatibility with API calls.
- **Auto-IP Capture**: Once the tunnel is active, the bot scrapes the public IP from the Playit logs and updates the `#server-information` channel automatically.

## ⚠️ Restricted Environments (School/Work Servers)
In environments without sudo or package managers:
1.  **Manual Binary Placement**: Manually place the `playit` binary in `/usr/local/bin` if the script cannot download it.
2.  **Docker Pre-install**: Ensure the administrator has already enabled the Docker daemon.
3.  **Local Pip**: Use `pip install -r requirements.txt --user` to avoid permission issues with global site-packages.

## 🛠️ Makefile Shortcuts
- `make build`: Rebuild the Docker image.
- `make up`: Start the bot in detached mode.
- `make logs`: Follow the combined bot and Minecraft logs.
- `make test`: Executes the 68-test suite in an isolated container.
