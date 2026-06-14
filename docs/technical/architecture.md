# Internal Architecture

MC-Bot is built on a modular, event-driven architecture that prioritizes process isolation and observability.

## 🏗️ System Components

### 1. The Runner (tmux)
Minecraft is not run directly by the Python process. Instead, it is spawned inside a **tmux** session named `minecraft`. 
- **Isolation**: If the bot crashes, the Minecraft server keeps running.
- **Access**: Admins can "attach" to the tmux session directly on the host machine for emergency maintenance.
- **Control**: The `src/server_interface.py` handles sending commands into the tmux session via RCON or standard input.

### 2. Log Dispatcher & Watcher
Instead of polling the server state, MC-Bot uses a reactive log-tailing system.
- **LogWatcher**: Continuously reads the Minecraft server logs.
- **LogDispatcher**: Parses these logs for specific patterns (logins, quits, deaths, version info) and dispatches events to the rest of the bot.
- **Observability**: This allows features like `JoinGuard` and `Console` to react in real-time to in-game events.

### 3. Cog Architecture
The bot's Discord features are organized into **Cogs**:
- `management`: Start/Stop/Restart, Server status.
- `backup`: Manual and automated backup triggers.
- `stats`: Player statistics and server performance.
- `link`: Account linking (`/link`, `/unlink`, `/verify`).
- `settings`: On-the-fly configuration updates.

## 🔄 Execution Flow

1.  **Boot**: `bot.py` loads configurations, initializes `MCLinkManager`, and starts the `LogWatcher`.
2.  **Server Start**: Admin runs `/start`. The bot spawns the Minecraft process in tmux and initializes the Playit tunnel.
3.  **Operation**: `LogWatcher` detects a player joining. `LogDispatcher` sends a `login_event` to `JoinGuard`.
4.  **JoinGuard**: Processes the login (Kicks if unverified, allows if premium/grace).
5.  **Shutdown**: Admin runs `/stop`. The bot sends a "stop" command to Minecraft, waits for the process to exit, and then cleans up the tmux session.

## 🧬 Core Technology Stack
- **Language**: Python 3.11+
- **Library**: `discord.py` (with App Commands / Slash Commands)
- **Database**: Flat-file JSON with process-safe locking.
- **Tunneling**: Playit.gg API.
- **Containerization**: Docker with multi-arch support (`amd64`/`arm64`).
