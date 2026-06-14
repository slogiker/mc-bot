# MC-Bot v3.1.1 — Documentation Hub

Welcome to the MC-Bot technical documentation. This project provides an all-in-one Dockerized solution for managing Minecraft servers via Discord, with a focus on security, observability, and ease of use.

## 🗺️ Documentation Map

### 🚀 Getting Started
- **[Installation & Setup](./setup/installation.md)**: Detailed requirements, universal installer, and the 8-step resumable Windows setup.
- **[Commands Reference](./commands.md)**: A comprehensive list of all slash commands, terminal commands, and permission mappings.

### 🛡️ Features
- **[Security (JoinGuard v2)](./features/security.md)**: Deep dive into the offline-mode protection, identity verification, anti-collision logic, and MD5 UUID "Lore".
- **[I18n (Internationalization)](./implementations/i18n-implementation.md)**: Details on the Slovenian localization and translation system.

### ⚙️ Technical Deep Dives
- **[Internal Architecture](./technical/architecture.md)**: How the bot uses tmux isolation, the LogDispatcher fan-out system, and reactive observability.
- **[Configuration System](./technical/configuration.md)**: Details on the atomic context managers, deadlock-free locking, and dual-file strategy.
- **[Offline Protection Logic](./implementations/offline-protection.md)**: Theoretical background on the authentication challenges.

### 🛠️ Maintenance & Troubleshooting
- **[Error Codes Index](./troubleshooting/errors.md)**: A comprehensive list of `BOT_XXX` and `Agent-XXX` error codes.
- **[Agent State](./internal/AGENT_STATE.md)**: Internal developer notes on the current project status and remediation phases.

---

## 🆕 What's New in v3.1.1?

The **"Observability & Polish"** update focused on hardening the system and improving the user experience:
- **Kick-Screen Codes**: Security verification codes are now shown directly in Minecraft, removing the dependency on Discord DMs.
- **Deadlock Fix**: The configuration engine was rebuilt from the ground up to be re-entrant and thread-safe.
- **Playit v1.0.10**: Standardized on the latest tunneling binary and legacy API for maximum reliability.
- **Slovenian Localization**: Added support for Slovenian translations in core interaction flows.
- **Multi-Distro Installer**: `install.sh` now supports a wider range of Linux families (RHEL, Arch, Alpine).

---

## 📝 Project Status & Roadmap

### 🔴 Critical / Active
- [x] **JoinGuard v2 Implementation**: Migration from DMs to kick-screen codes.
- [x] **Config Deadlock Resolution**: Re-entrant locking architecture.
- [ ] **Forge API Expansion**: Implementing reliable version fetching for Forge platforms.
- [ ] **Timeout Implementation**: Adding timeouts to all external API calls (Mojang, Modrinth).

### 🟠 High Priority
- [ ] **Chat Bridge**: Bi-directional Discord <-> Minecraft chat integration.
- [ ] **SQLite Migration**: Moving economy and events from JSON to a proper database for better concurrency.
- [ ] **Mascan Protection**: Hardening offline-mode against proxied connection spoofing.

### 🟡 Medium Priority
- [ ] **Uptime Statistics**: Tracking and displaying server longevity metrics.
- [ ] **Performance Dashboard**: Real-time TPS and resource usage trends in Discord.

---

## 📜 Version History (Recent)

### v3.1.1 — Observability & Polish (Current)
- Overhauled JoinGuard to use kick-screen codes.
- Fixed configuration engine deadlocks.
- Standardized Playit.gg to v1.0.10.
- Implemented Slovenian translations for core commands.
- Expanded installer to support multiple Linux distributions.

### v3.0.0 — Production Release
- Migrated to discord.py 2.0 with full Slash Command support.
- Introduced `LogDispatcher` for efficient log fan-out.
- Implemented `FileLock` for all configuration I/O.
- Added simulation mode (`--simulate`) for testing.

---
*Full historical reference and legacy notes are available in `docs/information.md.bak`.*
