# Internal Architecture

MC-Bot is built on a modular, event-driven architecture that prioritizes process isolation and observability. It is designed to run as an "all-in-one" solution where the bot, the Minecraft server, and the tunnel agent coexist in a single containerized environment.

## 🏗️ System Components

### 1. The Runner (tmux)
Minecraft is not run directly by the Python process. Instead, it is spawned inside a **tmux** session named `minecraft` inside the Docker container.
- **Isolation**: If the bot crashes, the Minecraft server keeps running. The bot distinguishes between intentional stops and crashes via a state file (`mc-server/bot_state.json`).
- **Access**: Admins can "attach" to the tmux session directly on the host machine for emergency maintenance (`docker exec -it mc-bot tmux attach -t minecraft`).
- **Control**: The `TmuxServerManager` (`src/server_tmux.py`) manages all tmux operations using `subprocess.run` (synchronous) wrapped in `asyncio.to_thread`.
- **Emergency Stop (/kill)**: If a graceful RCON stop hangs, `emergency_stop()` forcefully terminates the tmux session (`kill-session`).

### 2. Log Dispatcher & Watcher
Instead of polling the server state, MC-Bot uses a reactive log-tailing system.
- **LogWatcher**: Continuously reads the Minecraft server logs.
- **LogDispatcher**: A singleton that spawns exactly ONE `tail -F mc-server/logs/latest.log` subprocess. This prevents multiple cogs from wasting resources by spawning their own tail processes.
- **Fan-out Mechanism**: Reads stdout line-by-line and broadcasts each line to all subscriber `asyncio.Queue` instances.
- **Observability**: This allows features like `JoinGuard`, the `Console` cog (which streams to Discord), and `LogWatcher` (which scans for Authenticator events) to react in real-time.

### 3. Cog Architecture
The bot's Discord features are organized into **Cogs**, loaded dynamically from the `cogs/` directory:
- `management`: Start/Stop/Restart, Server status.
- `backup`: Manual and automated backup triggers.
- `stats`: Player statistics and server performance.
- `link`: Account linking (`/link`, `/unlink`, `/verify`).
- `settings`: On-the-fly configuration updates.
- `console`: Streams MC logs to Discord and handles raw `/cmd` input.
- `tasks`: Background maintenance tasks (crash checks, presence updates).

## 🔄 Execution Flow

### Bot Startup Sequence
1.  **Boot**: `bot.py` initializes `MCLinkManager`, `JoinGuard`, and `LogWatcher`.
2.  **Setup Hook**: Dynamically loads all cogs from `./cogs/*.py`.
3.  **Ready State**: `on_ready()` resolves the guild, ensures roles/channels exist via `SetupHelper`, and syncs slash commands.
4.  **Process Monitoring**: If the server is already running, the `LogDispatcher` and `LogWatcher` are started immediately.

### Server Lifecycle
1.  **Start**: Admin runs `/start`. The bot spawns the Minecraft process in tmux with specific RAM flags (`-Xms`, `-Xmx`).
2.  **Handshake**: The bot attempts to establish an RCON connection. Success updates the bot's presence to "Online".
3.  **Operation**: `LogWatcher` detects a player joining. `LogDispatcher` sends a `login_event` to `JoinGuard`.
4.  **Shutdown**: Admin runs `/stop`. The bot sends a "stop" command to Minecraft via RCON, waits for the process to exit, and then cleans up the tmux session.

## 🛠️ Development Workflow & Rules

To maintain the technical integrity of the MC-Bot project, developers should adhere to the following guidelines:
1.  **Centralized Utils**: Never import legacy functions from obsolete files. Stick entirely to `src/utils.py` for RCON commands and permission checks.
2.  **Config Isolation**: Always use the atomic context managers (`config.update_user_config()`) instead of raw file manipulation.
3.  **Simulation First**: Test new Discord commands using the `--simulate` flag before deploying to a live server environment.

## 🚢 Deployment & Networking

### Docker Architecture
```
Host machine
  └─ mc-bot container
       ├─ Python bot process
       ├─ tmux session "minecraft" (RCON on 127.0.0.1:25575)
       └─ tmux session "playit" (Tunnel agent)
```

### Volume Persistence
The following directories MUST be mounted as volumes to ensure data persists across container rebuilds:
- `./mc-server`: Minecraft world, properties, and logs.
- `./backups`: Automated and custom ZIP backups.
- `./data`: JSON configuration files and account links.
- `./logs`: Bot application logs.

### Process Health
The container includes a healthcheck that monitors the bot's process status. If the internal `psutil` checks fail repeatedly, Docker will automatically restart the container to restore service.
