# Security: JoinGuard v2

JoinGuard is the security gatekeeper for MC-Bot, specifically designed for **offline-mode** (cracked) servers where identity theft is a common risk. It ensures that every player joining the server is who they claim to be, even when the server cannot verify them against Mojang's official authentication servers.

## 🛡️ The Problem: Identity Theft & "Ghosting"
In offline-mode servers, anyone can join with any username (e.g., "Notch" or "Admin"). JoinGuard solves this by enforcing a mandatory link between a Minecraft account and a Discord account. Without this link and subsequent verification, the player is immediately expelled.

## 🔄 Verification Flow (v3.1.1)

1.  **Connection**: A player attempts to join the Minecraft server.
2.  **Recognition**: JoinGuard intercepts the login via `LogWatcher`. It checks if the username is:
    *   **Premium**: Verified against Mojang API. If confirmed, the player is allowed in silently.
    *   **Unlinked**: If no entry exists in `mc_links.json`, the player is kicked with instructions to use `/link`.
3.  **Challenge**: If linked but not premium (Offline account), the player is kicked with a **6-character secure code** shown directly on the kick screen.
4.  **Verification**: The player enters `/verify <code>` in the Discord `#commands` channel.
5.  **Grace Window**: Upon success, a **30-minute grace window** is opened. This allows the player to join freely without further challenges during their session or quick reconnects.

## 🚨 Advanced Protections

### Collision Protection (Anti-Impersonation)
A "Collision" occurs when an impersonator attempts to join using the name of a player who is already online. 
- **The Event**: Minecraft's engine kicks the first player.
- **The Detection**: JoinGuard identifies this specific kick reason in the logs.
- **The Mitigation**: The real player is immediately granted **emergency grace** (bypassing the next challenge) and sent a **High-Priority Discord DM Alert**.
- **The Result**: The real player can reclaim their spot instantly, while the impersonator is blocked by the fresh challenge.

### Anti-Spam & Rate Limiting
To prevent RCON overload and log pollution from automated "Join Bots":
- **Kick Cooldown**: Enforces a **60-second cooldown** between kicks for the same username.
- **Silent Ignore**: Subsequent join attempts during the cooldown are ignored by the bot (no kick issued, no processing wasted).

## 🛠️ Technical Details & "Lore"
- **MD5 Hash UUIDs**: For offline-mode whitelisting, the bot generates consistent local UUIDs based on a name-based MD5 hash, ensuring stability across sessions without Mojang dependency.
- **Cryptographic Security**: Codes are generated using Python's `secrets` module, ensuring they are not guessable.
- **Fail-Closed Design**: If the RCON connection or the Mojang API is unavailable, JoinGuard defaults to kicking the player to ensure maximum security (Fail-Closed).
- **Grace Logic**: Grace is tied to the `last_verified` timestamp in `mc_links.json`. It is NOT reset by logging out, ensuring the 30-minute window is absolute from the time of `/verify`.
