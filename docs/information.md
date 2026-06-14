# MC-Bot v3.1.1 — Technical Reference

This is the canonical source of truth for the MC-Bot project, following the major v3.1.1 "Observability & Security" update.

## 🚀 Quick Overview
MC-Bot is an "all-in-one" Dockerized solution for managing a Minecraft server via Discord. It combines a Python Discord bot, a Minecraft server (running in tmux), and a Playit.gg tunnel agent.

## 🛡️ Core Security: JoinGuard v2
The bot implements a sophisticated security gatekeeper for offline-mode servers to prevent impersonation.

- **Verification Flow**: 
  1. Player joins Minecraft.
  2. If not verified/premium, player is kicked with a **6-character secure code** shown on the kick screen.
  3. Player uses `/verify <code>` in Discord.
  4. Player is granted a **30-minute grace window** to join freely.
- **Collision Protection**: If an impersonator joins while the real player is online, the real player is alerted via DM and granted emergency grace to reconnect.
- **Anti-Spam**: 60-second cooldown between kicks for the same username.

## ⚙️ Configuration System
- **Split Configuration**:
  - `data/user_config.json`: User preferences (RAM, timezone, backups, role-based permissions).
  - `data/bot_config.json`: Persistent system state (Channel IDs, Guild ID, server metadata).
- **Concurrency**: Thread-safe and process-safe file locking using `filelock`.
- **Deadlock-Free**: v3.1.1 introduced an internal non-locking architecture to allow atomic updates without re-entrancy issues.

## 📦 Installation & Environments
- **Universal Installer**: `install/install.sh` supports Debian/Ubuntu, RHEL/CentOS, Arch Linux, and Alpine.
- **ARM64 Support**: Fully compatible with Raspberry Pi.
- **Automated Tunneling**: Built-in support for Playit.gg v1.0.10 with automated tunnel creation via API.
- **Resource Management**: Minimal footprint, but recommends **5GB+ disk space** for backups and Docker layers.

## 🛠️ Internal Architecture
- **Process Control**: Minecraft runs in a tmux session named `minecraft`. Control is abstracted via `src/server_interface.py`.
- **Log Dispatcher**: Centrally tails Docker logs and fans them out to multiple subscribers (JoinGuard, Console, Discord Stream).
- **Cogs**: Modular feature set including `management`, `backup`, `stats`, `link`, and `tasks`.

## 📜 Error Codes
- `Agent-001`: Config Corruption (Autofixed)
- `Agent-002`: RCON Connection Failure
- `Agent-003`: JoinGuard Challenge Timeout
- `Agent-004`: Playit Binary Missing
- `Agent-005`: Deadlock Detected (Fixed in v3.1.1)

---
*Legacy documentation archived in `docs/archive/`.*
