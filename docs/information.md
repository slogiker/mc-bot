# MC-Bot v3.1.1 — Documentation Hub

Welcome to the MC-Bot technical documentation. This project provides an all-in-one Dockerized solution for managing Minecraft servers via Discord, with a focus on security, observability, and ease of use.

## 🗺️ Documentation Map

### 🚀 Getting Started
- **[Installation & Setup](./setup/installation.md)**: Requirements, automated installer, and networking (Playit.gg) guide.
- **[Commands Reference](./commands.md)**: A complete list of slash commands and permissions.

### 🛡️ Features
- **[Security (JoinGuard v2)](./features/security.md)**: Deep dive into the offline-mode protection, kick codes, and anti-collision logic.
- **[I18n (Internationalization)](./implementations/i18n-implementation.md)**: Details on the Slovenian localization and translation system.

### ⚙️ Technical Deep Dives
- **[Internal Architecture](./technical/architecture.md)**: How the bot uses tmux, LogWatcher, and Cogs to manage the server process.
- **[Configuration System](./technical/configuration.md)**: Details on the thread-safe, deadlock-free config engine and `filelock` usage.
- **[Offline Protection Logic](./implementations/offline-protection.md)**: Theoretical background on the authentication challenges.

### 🛠️ Maintenance & Troubleshooting
- **[Error Codes Index](./troubleshooting/errors.md)**: A comprehensive list of `BOT_XXX` error codes and their meanings.
- **[Agent State](./internal/AGENT_STATE.md)**: Internal developer notes on the current project status and remediation phases.

---

## 🆕 What's New in v3.1.1?

The **"Observability & Polish"** update focused on hardening the system and improving the user experience:
- **Kick-Screen Codes**: Security verification codes are now shown directly in Minecraft, removing the dependency on Discord DMs.
- **Deadlock Fix**: The configuration engine was rebuilt to be re-entrant and thread-safe.
- **Playit v1.0.10**: Standardized on the latest tunneling binary and legacy API for maximum reliability.
- **Slovenian Localization**: Added support for Slovenian translations in core interaction flows.
- **Multi-Distro Installer**: `install.sh` now supports a wider range of Linux families (RHEL, Arch, Alpine).

---
*Legacy documentation archived in `docs/archive/`.*
