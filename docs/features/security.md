# Security: JoinGuard v2

JoinGuard is the security gatekeeper for MC-Bot, specifically designed for **offline-mode** (cracked) servers where identity theft is a common risk.

## 🛡️ The Problem: Identity Theft
In offline-mode servers, any player can join with any username. JoinGuard solves this by requiring a link between a Minecraft account and a Discord account, and providing a secondary verification step.

## 🔄 Verification Flow (v3.1.1)

1.  **Connection**: A player attempts to join the Minecraft server.
2.  **Recognition**: JoinGuard checks if the username is "Premium" (via Mojang API) or "Linked" (via `mc_links.json`).
    *   **Premium**: If the Mojang API confirms the account is real and owned, the player is allowed in silently.
    *   **Unlinked**: If the username is not linked to a Discord account, the player is kicked with instructions to use `/link`.
3.  **Challenge**: If linked but not premium, the player is kicked with a **6-character secure code** shown directly on the kick screen.
4.  **Verification**: The player enters `/verify <code>` in the Discord `#commands` channel.
5.  **Grace Window**: Upon success, the player is granted a **30-minute grace window**. They can reconnect and play freely during this time.

## 🚨 Advanced Protections

### Collision Protection (Anti-Impersonation)
If an impersonator attempts to join while the real player is already in-game:
1.  The real player is kicked by Minecraft's internal logic.
2.  JoinGuard detects this "Collision".
3.  The real player is immediately granted **emergency grace** and sent a **Discord DM Alert**.
4.  The real player can reconnect instantly without a new code.

### Anti-Spam
To prevent log spam and RCON overload, JoinGuard enforces a **60-second cooldown** between kicks for the same username. Subsequent join attempts during the cooldown are ignored silently.

## 🛠️ Technical Details
- **Codes**: Generated using `secrets.choice` for cryptographic security.
- **Persistence**: Grace windows and links are stored in `data/mc_links.json`.
- **Latency**: RCON commands are delayed by 1 second to ensure the player is fully connected before the kick is issued, preventing "ghost" sessions.
