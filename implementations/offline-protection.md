# Mascan-Proof Whitelist — Implementation Spec for mc-bot

## Overview

This document describes a secondary verification layer for the `mc-bot` Discord/Minecraft bot project.
The goal is to prevent impersonation attacks on an **offline-mode Minecraft server** where UUIDs are
derived deterministically from usernames, meaning any client claiming a known username gets the same
UUID as the real player.

The bot runs in Docker, controls a Minecraft server via RCON, watches server logs via a log watcher,
and communicates with players through Discord DMs.

> **Important constraint:** The server uses **playit.gg** for tunneling. This means the server always
> sees playit.gg relay IPs, not players' real IPs. IP-based verification is therefore useless and is
> NOT used in this implementation.

---

## Core Problem

```
Offline mode UUID = nameUUIDFromBytes("OfflinePlayer:" + username)
```

Anyone who knows a whitelisted username can connect and receive the exact same UUID as the real player.
The server cannot distinguish the real "steve" from an impersonator named "steve".

---

## Solution: Discord-Linked Accounts + Grace Window + DM Challenge

### Identity layers by account type

| Account Type | Verification Method |
|---|---|
| Premium (real Mojang account) | Mojang API UUID check — if username exists in Mojang DB, identity is proven. Silent pass. |
| Cracked (offline/TLauncher) | Discord link required + grace window logic + DM challenge on suspicious login |

### Grace window logic (cracked players only)

Because playit.gg makes IP memory impossible, sessions are tracked via a **disconnect timestamp**:

- When a player disconnects normally, `last_disconnect` is recorded
- If they reconnect within **5 minutes**, they pass silently (handles crashes, `/quit` + rejoin, server restarts)
- If they reconnect **after 5 minutes**, the bot kicks them and sends a Discord DM challenge
- The real player reacts ✅ to approve or ❌ to deny within **2 minutes**
- No response within 2 minutes = **auto-denied**

### Full login decision tree

```
Player joins
│
├─ Not in mc_links.json → kick "Join Discord and use /link"
│
├─ Premium (Mojang API returns 200 for username)
│   └─ Always allow — Mojang account = cryptographic identity proof
│   └─ NOTE: If Mojang API is down/slow (5s timeout) → fail open, treat as premium
│
└─ Cracked
    └─ is_within_grace(username)?
        ├─ YES → silent pass
        └─ NO  → kick "Session expired. Check Discord DMs."
                 send DM challenge to linked Discord user
                 ├─ ✅ react within 2 min → reset last_disconnect, DM "reconnect now"
                 ├─ ❌ react anytime     → deny, DM "denied"
                 └─ timeout 2 min        → auto-deny, DM "auto-denied"
```

### Collision detection (impersonation alert)

When user2 connects as "steve" while the real steve is online, Minecraft kicks the real steve with:
```
steve lost connection: You logged in from another location
```

The bot detects this log line and:
1. Records `last_disconnect` for steve (starts 5 min grace window so real steve can reconnect freely)
2. DMs steve123 on Discord with a 🚨 intrusion alert explaining what happened

---

## File Structure

```
mc-bot/
├── data/
│   └── mc_links.json          ← persistent link + session storage
├── src/
│   ├── mc_link_manager.py     ← all read/write operations on mc_links.json
│   ├── mojang.py              ← async Mojang API premium check
│   ├── log_watcher.py         ← tails logs/latest.log, fires callbacks
│   └── join_guard.py          ← main brain: handles all login events
└── cogs/
    └── link.py                ← Discord slash commands: /link /unlink /linked /forceunlink
```

---

## Data Schema — `data/mc_links.json`

```json
{
  "links": {
    "<discord_user_id>": {
      "mc_username": "steve",
      "last_disconnect": 1710000000
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `discord_user_id` | string (key) | Discord user's snowflake ID |
| `mc_username` | string | Exact Minecraft username (case-preserved) |
| `last_disconnect` | int \| null | Unix timestamp of last disconnect. null = never connected |

**Rules:**
- One Discord account → one MC username max
- One MC username → one Discord account max (enforced on `/link`)
- File is written with `filelock.FileLock` to prevent concurrent write corruption

---

## Module: `src/mc_link_manager.py`

Handles all read/write to `mc_links.json`. No Discord or RCON logic here.

### Functions

```python
get_entry_by_discord(discord_id: str) -> dict | None
```
Returns the full entry for a Discord user or `None`.

```python
get_entry_by_username(mc_username: str) -> tuple[str, dict] | tuple[None, None]
```
Reverse lookup. Returns `(discord_id, entry)` or `(None, None)`. Case-insensitive match.

```python
link(discord_id: str, mc_username: str) -> tuple[bool, str]
```
Creates a new link. Returns `(True, mc_username)` on success or `(False, error_message)` on failure.
Fails if: Discord user already linked, or MC username already claimed by someone else.

```python
unlink(discord_id: str) -> tuple[bool, str]
```
Removes the link. Returns `(True, mc_username)` or `(False, error_message)`.

```python
admin_unlink_by_username(mc_username: str) -> tuple[bool, str]
```
Admin-facing unlink by MC username instead of Discord ID. Delegates to `unlink()`.

```python
record_disconnect(mc_username: str)
```
Sets `last_disconnect` to `int(time.time())` for the given username. Called on: normal leave, collision.

```python
is_within_grace(mc_username: str) -> bool
```
Returns `True` if `time.time() - last_disconnect <= 300` (5 minutes = `GRACE_SECONDS`).

### Constants
```python
GRACE_SECONDS = 5 * 60   # 300 seconds
LINKS_PATH    = "data/mc_links.json"
LOCK_PATH     = "data/mc_links.json.lock"
```

---

## Module: `src/mojang.py`

Single async function. Queries the Mojang API to determine if a username belongs to a real premium account.

```python
async def is_premium(username: str) -> bool
```

- Calls `https://api.mojang.com/users/profiles/minecraft/{username}`
- HTTP 200 → `True` (premium)
- HTTP 404 → `False` (cracked / username not registered)
- Any other status, timeout, or exception → `True` (fail open — agreed design decision)
- Timeout: 5 seconds (`aiohttp.ClientTimeout(total=5)`)
- Uses `aiohttp` (already a likely dependency; add if missing)

**Fail-open rationale:** Mojang API outages are rare. Failing open means legitimate premium players
are never blocked due to upstream issues. The worst case is a cracked player impersonating a premium
username during an outage — acceptable tradeoff for a private server.

---

## Module: `src/log_watcher.py`

Tails `logs/latest.log` in a background asyncio task. Seeks to end-of-file on startup to avoid
replaying old events.

### Regex patterns

```python
# Alex[/93.184.216.34:60123] logged in with entity id 89 at ([world] 0.0, 70.0, 0.0)
LOGIN_RE = re.compile(
    r"\[.*?INFO\].*?:\s+(\w+)\[\/[0-9.:]+\] logged in"
)

# Alex left the game
LEAVE_RE = re.compile(
    r"\[.*?INFO\].*?:\s+(\w+) left the game"
)

# Steve lost connection: You logged in from another location
# Fires when a second client connects with the same username, booting the first
COLLISION_RE = re.compile(
    r"\[.*?INFO\].*?:\s+(\w+) lost connection: You logged in from another location"
)
```

> **Verification note:** The collision regex matches the standard Paper/Spigot wording.
> If the server fork uses different wording, update `COLLISION_RE` accordingly.
> Test by connecting with the same username twice and checking the raw log line.

### Constructor

```python
LogWatcher(log_path: str, on_login, on_leave, on_collision)
```

| Callback | Signature | When |
|---|---|---|
| `on_login` | `async (username: str)` | `logged in` line matched |
| `on_leave` | `async (username: str)` | `left the game` matched |
| `on_collision` | `async (username: str)` | `lost connection: You logged in from another location` matched |

**Collision is checked before login/leave** so the more specific pattern always wins on the same line.

---

## Module: `src/join_guard.py`

The main brain. Instantiated once at bot startup. Owns the `LogWatcher` and all pending challenge state.

### Constructor

```python
JoinGuard(
    bot: discord.Client,
    rcon,                        # existing RCON wrapper with async .send(cmd) method
    log_path: str,               # path to logs/latest.log inside the server volume
    exempt_usernames: list[str]  # usernames that always pass (e.g. server admin)
)
```

### Internal state

```python
self._pending: dict[str, dict]
# username → {
#     "discord_id": str,
#     "dm_message": discord.Message,
#     "expires_at": float  (unix timestamp)
# }
```

One entry per in-flight DM challenge. Removed on: ✅ approval, ❌ denial, timeout, or player leave.

### Methods

```python
async def start()
```
Starts the log watcher background task. Call once in `setup_hook` or `on_ready`.

```python
async def on_login(username: str)
```
Main entry point per login event. Runs the full decision tree (see above).

```python
async def on_leave(username: str)
```
Records disconnect timestamp. Clears any pending challenge for that username.

```python
async def on_collision(username: str)
```
Called when the real player is booted by a second connection with same username.
Records disconnect (starts grace window). Sends 🚨 DM alert to linked Discord user.

```python
async def handle_reaction(payload: discord.RawReactionActionEvent)
```
Must be called from `on_raw_reaction_add` bot event. Matches reaction to pending challenge by
`(discord_id, message_id)`. Handles ✅ and ❌ emojis only. Ignores bot's own reactions.

**On ✅:** Calls `record_disconnect()` to reset grace window, edits DM to green "Verified", removes from pending.
**On ❌:** Edits DM to red "Denied", removes from pending.

```python
async def _send_challenge(discord_id: str, username: str)
```
Sends the orange DM embed with ✅/❌ reactions. Schedules `_auto_deny` task.

```python
async def _auto_deny(username: str, expires_at: float)
```
Waits `CHALLENGE_TIMEOUT + 1` seconds. If the challenge is still pending with same `expires_at`,
edits the DM to red "Auto-denied" and removes from pending.

```python
async def _kick(username: str, reason: str)
```
Executes `kick {username} {reason}` via RCON. Reason appears on the player's disconnect screen.

### Constants
```python
CHALLENGE_TIMEOUT = 120  # 2 minutes
```

---

## Cog: `cogs/link.py`

All slash commands. Registered as a standard discord.py Cog.

| Command | Access | Description |
|---|---|---|
| `/link <mc_username>` | Everyone | Link your Discord account to a Minecraft username |
| `/unlink` | Everyone | Remove your link |
| `/linked` | Everyone | Check which MC username your Discord is linked to |
| `/forceunlink <mc_username>` | Admin only (`administrator` permission) | Force-remove any link by MC username |

All commands respond `ephemeral=True` (only visible to the caller) except `/forceunlink` which is visible to admins in the channel.

All responses use `discord.Embed` with green (success) or red (failure) color.

---

## Bot Wiring — Startup

```python
# In setup_hook or on_ready:
from src.join_guard import JoinGuard
from cogs.link import LinkCog

guard = JoinGuard(
    bot=bot,
    rcon=server_manager.rcon,
    log_path="data/server/logs/latest.log",  # adjust to actual volume mount path
    exempt_usernames=["YourAdminUsername"]
)
await guard.start()
await bot.add_cog(LinkCog(bot))

# Somewhere in your bot file:
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await guard.handle_reaction(payload)
```

---

## Dependencies

| Package | Used in | Notes |
|---|---|---|
| `discord.py 2.x` | all | Already in project |
| `aiohttp` | `mojang.py` | For async HTTP to Mojang API |
| `filelock` | `mc_link_manager.py` | Already in project (used for config) |

---

## Security Properties

| Attack vector | Result |
|---|---|
| Mascan discovers "steve" is online, connects as "steve" | Kicked — outside grace window, DM goes to real steve123 who denies |
| User2 joins as "steve" while real steve is online | Real steve gets collision alert + grace window. User2 gets kicked + challenge sent, real steve denies |
| User2 joins as "steve" within 5 min of real steve disconnecting | User2 passes silently — **known limitation, acceptable tradeoff** |
| Unknown username with no Discord link | Kicked immediately with instructions |
| Premium account impersonation | Impossible — Mojang API confirms ownership |
| Mojang API down | Fail open — all players treated as premium, no one blocked |
| User has DMs closed | Stays blocked (can't receive challenge). User must open DMs or contact admin |

### Known limitation — grace window race condition

If user2 connects within 5 minutes of the real steve disconnecting, they pass silently.
This is a deliberate tradeoff — eliminating it requires either a Minecraft plugin (AuthMe/nLogin)
or requiring all players to use premium accounts.

For a private friend server this is acceptable. For public servers, use a plugin instead.

---

## Deployment Checklist

- [ ] `data/mc_links.json` created (can be empty `{"links": {}}`)
- [ ] `aiohttp` added to `requirements.txt`
- [ ] `log_path` in `JoinGuard` points to the correct volume-mounted log file
- [ ] `exempt_usernames` includes the server admin's MC username
- [ ] `on_raw_reaction_add` event wired to `guard.handle_reaction()`
- [ ] `LinkCog` registered in bot startup
- [ ] Verified collision log line wording matches `COLLISION_RE` on your specific server fork
- [ ] Players informed they must `/link` before joining

---

## Player-Facing Flow (what to tell your users)

1. Join the Discord server
2. Run `/link YourMinecraftUsername` in Discord
3. Connect to the Minecraft server as normal
4. If joining after a long break (>5 min since last disconnect), check Discord DMs and react ✅

If you get kicked with "Account not verified" → you haven't linked yet.
If you get kicked with "Session expired" → check Discord DMs for a verification request.