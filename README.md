# 🎮 MC-Bot `v3.0.0`

> **A Discord-powered Minecraft server manager that runs entirely inside Docker.**

MC-Bot lets you and your friends manage a full Minecraft Java server from Discord — no SSH, no port forwarding, no technical knowledge required. Just clone, run the installer, and type `/setup` in Discord.

---

## ✨ Features

### 🎛️ Full Server Control from Discord
Start, stop, restart, and monitor your server with slash commands or interactive button panels. Includes a `/kill` command for emergency hard-stops if the server hangs.

### 🌐 Automatic Public Tunneling
Integrated **Playit.gg** support exposes your server to the Internet without touching your router. The installer handles account creation — you just open one link and click "Claim".

### 📡 Live Log Streaming & Filtering
Server console output is streamed live to Discord. The `/logs` command features interactive buttons to filter for Chat, Joins/Leaves, Errors, or Raw output.

### 💾 Automated & Manual Backups
Daily scheduled backups with configurable retention, plus on-demand backups via `/backup` with direct Discord file downloads and filename autocomplete.

### 🔐 Role-Based Permissions
Full permission system — restrict commands by Discord role. Configure which roles can manage the server core, mods, or run console commands.

### 🟢 Smart Presence
The bot's Discord status reflects the real server state: 🟢 Online (verified via RCON), 🌙 Starting/Stopping, 🔴 Offline. It proactively warns if RCON is unavailable.

### 🧩 Multi-Platform Support
Setup wizard supports **Paper**, **Vanilla**, and **Fabric** servers. It automatically detects the correct folders for mods/plugins and skips mod steps for Vanilla.

### 📊 Player Statistics & Linking
View playtime, deaths, and more via `/stats`. Features a **Player Linking** system to protect offline-mode servers from impersonation using Discord DM challenges.

---

## 🚀 Getting Started (From Absolute Zero)

This section walks you through every step from nothing to a running server.

### Step 1 — Create a Discord Application
1. Go to [discord.com/developers/applications](https://discord.com/developers/applications).
2. Click **"New Application"**, name it (e.g. `MC-Bot`), and click **"Create"**.

### Step 2 — Installation Settings
1. Click **"Installation"** in the sidebar.
2. Set **"Install Link"** to **None** and click **"Save Changes"**.

### Step 3 — Configure the Bot
1. Click **"Bot"** in the sidebar.
2. Click **"Reset Token"** → copy and save it safely.
3. Turn **OFF** the **"Public Bot"** toggle.
4. Scroll down to **"Privileged Gateway Intents"** and turn **ON**:
   - **Server Members Intent** (for permissions)
   - **Message Content Intent** (for chat triggers/bridge)
5. Click **"Save Changes"**.

### Step 4 — Invite the Bot
1. Click **"OAuth2"** → **"URL Generator"**.
2. Check `bot` and `applications.commands`.
3. Check `Administrator` (simplest) or select `Manage Roles`, `Manage Channels`, `Send Messages`, `Embed Links`, `Attach Files`.
4. Copy the URL, open it in your browser, and authorize it for your server.

### Step 5 — Prepare Your Machine
- **OS:** Linux (Ubuntu/Debian recommended) or Windows with WSL2.
- **RAM:** 4 GB+ recommended.
- **Disk:** 5 GB+ free.

### Step 6 — Install MC-Bot

**Linux:**
```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot
chmod +x install/install.sh
./install/install.sh
```

**Windows (WSL2):**
Double-click `install/install.bat`. It will help you set up WSL2 and run the Linux installer inside an Ubuntu environment.

### Step 7 — Run the Setup Wizard
Once the bot is online, go to the new `#commands` channel and type:
```
/setup
```
Follow the interactive steps to install your preferred Minecraft version.

---

## 📋 Commands at a Glance

| Command | What it does |
|---------|-------------|
| `/start` | Start the Minecraft server |
| `/stop` | Graceful shutdown via RCON |
| `/kill` | Emergency hard-kill of the server process |
| `/control` | Interactive control panel (buttons) |
| `/status` | Show online/offline + player list |
| `/logs` | View server console with interactive filters |
| `/players` | List online players (with log-based fallback) |
| `/mod_search` | Search and install mods/plugins from Modrinth |
| `/backup` | Create or download world backups |
| `/stats` | View player statistics and achievements |

For the complete list, see [`docs/commands.md`](docs/commands.md).

---

## 🏗️ Architecture

Everything runs in **one Docker container**. The bot communicates with the Minecraft server via **RCON** (localhost only) and controls the process via **tmux**. Logs are streamed via a high-performance `tail -F` fan-out system.

---

## ❓ FAQ

**Q: Which versions are supported?**
A: All Java Edition versions. The setup wizard fetches the latest versions for Paper, Vanilla, and Fabric dynamically.

**Q: How do I add mods?**
A: Use `/mod_search` to find mods on Modrinth and install them with one click. For Fabric/Forge, put `.jar` files in `mc-server/mods/`. For Paper, use `mc-server/plugins/`.

**Q: What if RCON goes down?**
A: The bot uses a log-based fallback to track players and offers a `/kill` command to forcefully stop the server if it hangs.

**Q: Where is my data?**
A: Your world lives in `mc-server/`, config in `data/`, and backups in `backups/`. All are persisted via Docker volumes.

---

## 🧪 Testing

```bash
make test  # Runs 48+ unit tests in Docker
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [`docs/information.md`](docs/information.md) | Full technical reference, architecture, and version history |
| [`docs/commands.md`](docs/commands.md) | Complete command cheatsheet with permissions |

---

## 📄 License

[MIT](LICENSE) — Made by slogiker.
