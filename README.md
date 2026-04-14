# 🎮 MC-Bot

> **A Discord-powered Minecraft server manager that runs entirely inside Docker.**

MC-Bot lets you and your friends manage a full Minecraft Java server from Discord — no SSH, no port forwarding, no technical knowledge required. Just clone, run the installer, and type `/setup` in Discord.

---

## ✨ Features

### 🎛️ Full Server Control from Discord
Start, stop, restart, and monitor your server with slash commands or interactive button panels — no terminal needed.

### 🌐 Automatic Public Tunneling
Integrated **Playit.gg** support exposes your server to the Internet without touching your router. The installer handles account creation — you just open one link and click "Claim".

### 📡 Live Log Streaming
Server console output, chat messages, player joins/leaves, and death events are streamed live to dedicated Discord channels.

### 💾 Automated & Manual Backups
Daily scheduled backups with configurable retention, plus on-demand backups via `/backup` with one-click download links.

### 🔐 Role-Based Permissions
Full permission system — restrict commands by Discord role. Configure which roles can start the server, manage backups, or run console commands.

### 🟢 Dynamic Presence
The bot's Discord status reflects the real server state: 🟢 Online, 🌙 Starting/Stopping, 🔴 Offline.

### 🧩 Multi-Platform Support
Setup wizard supports **Paper**, **Vanilla**, and **Fabric** servers — choose your version and platform in Discord.

### 📊 Player Statistics
View playtime, deaths, kills, and more via `/stats` — reads directly from NBT data files with Mojang API skin thumbnails.

### ⏰ Scheduled Events
Create server events with automatic 24h and 1h reminders sent to Discord.

### 🤖 Chat Triggers
Define keyword → RCON command triggers so your server reacts to in-game chat automatically.

---

## 🚀 Getting Started (From Absolute Zero)

This section walks you through every step from nothing to a running server. Even if you've never used Discord bots or Docker before, follow these steps in order.

---

### Step 1 — Create a Discord Bot

You need to create a Discord "application" and get a bot token. This is free and takes about 3 minutes.

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and log in with your Discord account.
2. Click **"New Application"** in the top-right corner.
3. Give it a name (e.g. `MC-Bot`) and click **"Create"**.
4. In the left sidebar, click **"Bot"**.
5. Click **"Reset Token"** → copy and save the token somewhere safe. **You will need this during installation.** Treat it like a password — never share it publicly.

> **Lost your token?** You can always go back to the Bot page and reset it to get a new one.

---

### Step 2 — Enable Required Bot Intents

Still on the **Bot** page, scroll down to **"Privileged Gateway Intents"** and enable **both** of these:

| Intent | Why it's needed |
|--------|----------------|
| **Server Members Intent** | Required to read Discord role membership for the permission system |
| **Message Content Intent** | Required for the bot to read messages in channels |

Click **"Save Changes"** after enabling them.

---

### Step 3 — Invite the Bot to Your Server

1. In the left sidebar, click **"OAuth2"** → **"URL Generator"**.
2. Under **"SCOPES"**, check these two boxes:

   - ☑ `bot`
   - ☑ `applications.commands`

3. A **"BOT PERMISSIONS"** section will appear below. Check the following permissions:

   **General Permissions**
   - ☑ Manage Roles *(creates MC Owner / MC Admin / MC Player roles during setup)*
   - ☑ Manage Channels *(creates the bot's Discord channels during setup)*
   - ☑ View Channels

   **Text Permissions**
   - ☑ Send Messages
   - ☑ Send Messages in Threads
   - ☑ Create Public Threads
   - ☑ Manage Messages
   - ☑ Embed Links
   - ☑ Attach Files
   - ☑ Read Message History
   - ☑ Mention @everyone, @here, and All Roles *(for event reminders)*
   - ☑ Add Reactions
   - ☑ Use External Emojis

   > **Shortcut:** If you're setting this up just for a private friends server, you can check **Administrator** under General Permissions instead of selecting individual permissions. This is simpler but gives the bot full server access.

4. Scroll to the bottom and copy the generated **URL**.
5. Open the URL in your browser, select your server from the dropdown, and click **"Authorize"**.

The bot will now appear in your server's member list (shown as offline until you run it).

---

### Step 4 — Prepare Your Machine

You need a computer or VPS to host the bot and server. Requirements:

- **OS:** Linux (Ubuntu/Debian recommended) or Windows with WSL2
- **RAM:** At least 4 GB (2 GB for Minecraft + 100 MB for bot + OS overhead)
- **Disk:** At least 5 GB free
- **Internet:** Required for Playit.gg tunnel (or open port 25565 manually)

Docker is installed automatically by the installer if it's not already present.

---

### Step 5 — Install MC-Bot

**Linux:**

```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot
chmod +x install/install.sh
./install/install.sh
```

**Windows (WSL2):**

> **Warning:** Windows support is not stable and may require additional manual tweaks to get working. Linux is strongly recommended.

```
install\install.bat
```

The installer will:

1. Install Docker if missing
2. Prompt for your **Discord Bot Token** (from Step 1)
3. Ask if you want **Playit.gg** public access (recommended for most users)
   - If yes — a claim link will appear after startup; open it, create a free account, click Claim
   - If you already have a Playit.gg key — paste it to skip the claim flow
4. Auto-generate a secure RCON password
5. Build and start the Docker container

---

### Step 6 — Run the Setup Wizard

When the container starts, the bot automatically creates dedicated channels (`#mc-commands`, `#mc-console`, `#mc-debug`, `#mc-info`, `#mc-backups`) and three Discord roles (`MC Owner`, `MC Admin`, `MC Player`) before anything else.

Once you see these channels, go to **`#mc-commands`** and type:

```
/setup
```

The bot only listens for commands in that channel. The setup wizard will guide you through:

1. Choosing a Minecraft platform (**Paper**, **Vanilla**, or **Fabric**)
2. Picking a version
3. Setting difficulty, world seed, max players, and RAM
4. Optionally adding mods or plugins by Modrinth slug
5. Installing the server and starting it for the first time

---

### Step 7 — Connect and Play

Once setup completes, type `/ip` in Discord. Your friends paste that address into Minecraft's multiplayer screen. No port forwarding needed if you're using Playit.gg.

---

## 🛠️ Quick Start (If You Already Have a Bot Token)

```bash
git clone https://github.com/slogiker/mc-bot.git
cd mc-bot
chmod +x install/install.sh
./install/install.sh
```

Then run `/setup` in Discord.

### Windows

```
install\install.bat
```

See [`docs/information.md`](docs/information.md) for the detailed Windows WSL2 + Docker setup walkthrough.

---

## 📋 Commands at a Glance

| Command | What it does |
|---------|-------------|
| `/start` | Start the Minecraft server |
| `/stop` | Graceful shutdown |
| `/restart` | Stop + start with delay |
| `/status` | Show online/offline + player count |
| `/ip` | Get the public Playit.gg address |
| `/players` | List online players |
| `/backup [name]` | Create a world backup |
| `/setup` | Interactive server install wizard |
| `/stats [player]` | Player statistics (playtime, deaths, etc.) |
| `/cmd <command>` | Run a raw RCON command (owner only) |
| `/help` | Show all commands you have permission to use |

For the complete list, see [`docs/commands.md`](docs/commands.md).

---

## 🏗️ Architecture

Everything runs in **one Docker container**:

```
┌─────────────────────────────────────┐
│          Docker: mc-bot             │
│                                     │
│  ┌──────────┐   ┌────────────────┐  │
│  │ Python   │   │ Java 21        │  │
│  │ bot.py   │──►│ server.jar     │  │
│  │ (discord │   │ (tmux session  │  │
│  │  .py)    │   │  "minecraft")  │  │
│  └──────────┘   └────────────────┘  │
│       │                             │
│       │ RCON (127.0.0.1:25575)      │
│       │                             │
│  ┌──────────┐                       │
│  │ playit   │  (tmux session        │
│  │ agent    │   "playit")           │
│  └──────────┘                       │
│                                     │
│  Volumes: data/ mc-server/ backups/ │
└─────────────────────────────────────┘
```

- **Bot** runs as the main Python process
- **Minecraft server** runs inside a `tmux` session named `minecraft`
- **Playit tunnel** runs inside a `tmux` session named `playit`
- Communication between bot and server uses **RCON** on localhost (never exposed)
- Persistent data lives in Docker volume mounts: `data/`, `mc-server/`, `backups/`, `logs/`

---

## 🔄 Updating

```bash
python install/update.py
```

Pulls the latest code from GitHub and rebuilds the container automatically.

---

## 🐳 Useful Docker Commands

```bash
# View live logs
docker compose logs -f mc-bot

# Open a shell inside the container
docker exec -it mc-bot /bin/bash

# Attach to the Minecraft server console
# (Detach with Ctrl+B, then D)
docker exec -it mc-bot tmux attach -t minecraft

# Attach to the Playit tunnel session
docker exec -it mc-bot tmux attach -t playit

# Restart the container
docker compose restart mc-bot

# Stop everything
docker compose down

# Full rebuild from scratch
docker compose build --no-cache && docker compose up -d
```

---

## ❓ FAQ

**Q: Do I need to know anything about servers or Docker to use this?**
A: No. Run the installer, paste your Discord bot token, and type `/setup` in Discord. That's it.

**Q: How do friends connect to my server?**
A: Type `/ip` in Discord — the bot will show the Playit.gg address. Your friends paste that into Minecraft's multiplayer screen. No port forwarding needed.

**Q: Which Minecraft versions are supported?**
A: Java Edition only. The setup wizard lets you pick any version and choose between **Paper**, **Vanilla**, or **Fabric** server platforms.

**Q: Can I install mods or plugins?**
A: Yes. During the setup wizard you can specify Modrinth project slugs. For Paper servers, add plugins; for Fabric servers, add mods. You can also manually drop `.jar` files into the `mc-server/plugins/` or `mc-server/mods/` folder.

**Q: How much RAM does this use?**
A: The bot itself uses ~100MB. The Minecraft server RAM is configurable during setup (default 2–4 GB). A host with at least 4 GB of total RAM is recommended.

**Q: Is there a player limit?**
A: You set the max player count during setup. The default is 20 — you can change it anytime via `server.properties`.

**Q: How do backups work?**
A: The bot runs automatic daily backups (configurable time in `data/user_config.json`) and keeps them for 7 days by default. Use `/backup` for manual backups. All backups are stored in the `backups/` folder and can be downloaded via `/backup_download`.

**Q: What if my server crashes?**
A: The bot runs a background crash checker every 30 seconds. If the server goes down unexpectedly, it automatically restarts it and notifies you in the debug channel. After 2 failed restarts, it stops and pings the owner.

**Q: What if the Playit tunnel goes down?**
A: The bot monitors the Playit tmux session every 30 seconds. If it dies, the bot auto-restarts it (up to 2 attempts). If both attempts fail, the server owner gets pinged in Discord with instructions to fix it manually.

**Q: The bot is in my server but commands don't appear — what do I do?**
A: Make sure you checked both `bot` and `applications.commands` scopes when generating the invite URL (Step 3). If the bot is already in the server, kick it and re-invite using a corrected URL. Then run `/sync` in Discord after the bot starts.

**Q: The bot says "Missing Permissions" during setup — what do I do?**
A: The bot needs **Manage Roles** and **Manage Channels** permissions. Either re-invite using the correct permissions from Step 3, or go to Server Settings → Roles → find the bot's role and enable those permissions manually.

**Q: Can I run this on a Raspberry Pi?**
A: Technically yes if it's a Pi 4 (4GB+) running 64-bit OS with Docker installed, but performance will be limited. A small VPS or old laptop is a better option.

**Q: How do I change server settings after setup?**
A: Edit `mc-server/server.properties` directly, or use `/cmd` to run RCON commands. For bot settings (RAM, backup schedule, permissions), edit `data/user_config.json`.

**Q: Can multiple people manage the server?**
A: Yes. The permission system uses Discord roles. By default, the server owner gets full access, "MC Admin" gets management commands, and "MC Player" gets basic info commands. Customize roles in `data/user_config.json`.

**Q: I don't want Playit.gg. Can I use my own IP?**
A: Yes. Skip the Playit setup during installation and forward port `25565` on your router instead. Players connect using your public IP.

**Q: Where is my world data stored?**
A: In the `mc-server/world/` directory on your host machine. It's a Docker volume mount, so your world persists even if you rebuild the container.

**Q: How do I completely reset the server?**
A: Delete the `mc-server/` folder and run `/setup` again in Discord. To also reset the bot configuration, delete `data/bot_config.json`.

---

## 🧪 Testing

The project includes a Docker-based test suite (48 tests across config validation, backup manager, version fetcher, and utilities):

```bash
# Run all tests in Docker (auto-cleanup)
make test

# Verbose output with full tracebacks
make test-verbose

# Run a single test file
make test-single FILE=tests/test_config.py
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [`docs/information.md`](docs/information.md) | Full architecture reference, config system, cog docs, version history |
| [`docs/commands.md`](docs/commands.md) | Complete command cheatsheet with permissions |

---

## 📄 License

[MIT](LICENSE) — use it however you want.
