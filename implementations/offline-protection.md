# JoinGuard Reimplementation — AI Agent Instructions

## Context

This is the `mc-bot` project — a Discord bot that manages a Minecraft server running inside Docker.
You are rewriting the offline-mode impersonation protection system.

The current implementation uses Discord DMs + reaction buttons for verification.
The new implementation uses a code shown in the Minecraft **kick reason screen** + a `/verify` slash command in Discord.

Read this entire document before touching any file.

---

## What you are changing and why

| Old behaviour | New behaviour |
|---|---|
| Verification code sent via Discord DM | Code shown in Minecraft kick reason (visible only to the kicked player) |
| "Verify Identity" button in DM | `/verify <code>` slash command in Discord `#commands` channel |
| `random.randint(1000, 9999)` — 9000 combinations | `secrets.choice(alphabet)` × 6 — 1.6 billion combinations, cryptographically secure |
| Grace period: 5 min from last disconnect | Grace period: 30 min from last successful `/verify` |
| Challenge cleared when player disconnects | Challenge stays active until it expires (5 min) |
| Race condition: lock released between read and write | Fixed: entire read-modify-write under one lock |
| No anti-spam | 60-second cooldown per username between kicks |

---

## Files to modify

```
src/mc_link_manager.py     — FULL REPLACE
src/join_guard.py          — FULL REPLACE
src/utils_views.py         — DELETE (no longer needed, DM buttons removed)
cogs/link.py               — FULL REPLACE
implementations/offline-protection.md  — FULL REPLACE
```

Do NOT touch any other files unless a compile/import error forces you to.

---

## File 1 — `src/mc_link_manager.py` (FULL REPLACE)

```python
import json
import os
import asyncio
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────────────────
# Schema per record (keyed by str(discord_id)):
# {
#     "mc_username":     str,   — exact username, case-preserved
#     "is_premium":      bool,  — True = Mojang API confirmed real account
#     "linked_at":       str,   — ISO-8601 UTC timestamp
#     "last_verified":   float | null,  — unix timestamp of last successful /verify
#     "last_disconnect": float | null,  — unix timestamp of last MC disconnect
# }
# ──────────────────────────────────────────────────────────────────────────────

GRACE_SECONDS   = 30 * 60   # 30 minutes — how long after /verify the player can rejoin freely
LINKS_PATH      = "data/mc_links.json"
LOCK_PATH       = "data/mc_links.json.lock"


class MCLinkManager:
    def __init__(self, data_file: str = LINKS_PATH):
        self.data_file = data_file
        self.lock = asyncio.Lock()
        self._ensure_file()

    # ── File helpers ──────────────────────────────────────────────────────────

    def _ensure_file(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w") as f:
                json.dump({}, f)

    def _read_sync(self) -> dict:
        try:
            with open(self.data_file, "r") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except FileNotFoundError:
            return {}

    def _write_sync(self, data: dict):
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=4)

    async def _read(self) -> dict:
        async with self.lock:
            return await asyncio.to_thread(self._read_sync)

    async def _write(self, data: dict):
        async with self.lock:
            await asyncio.to_thread(self._write_sync, data)

    # ── Read helpers ──────────────────────────────────────────────────────────

    async def get_link_by_discord(self, discord_id: int) -> dict | None:
        """Return entry for a Discord ID, or None."""
        data = await self._read()
        return data.get(str(discord_id))

    async def get_link_by_mc(self, mc_username: str) -> dict | None:
        """Return entry (including discord_id key) for an MC username. Case-insensitive."""
        data = await self._read()
        for d_id, entry in data.items():
            if entry["mc_username"].lower() == mc_username.lower():
                return {"discord_id": int(d_id), **entry}
        return None

    # ── Write helpers ─────────────────────────────────────────────────────────

    async def link_account(self, discord_id: int, mc_username: str, is_premium: bool = False):
        """
        Link a Discord account to a Minecraft username.
        If another Discord account already owns this MC username, that link is removed first.
        Entire read-modify-write is held under one lock to prevent race conditions.
        """
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)

            # Remove any existing link for this MC username (username theft prevention)
            data = {
                k: v for k, v in data.items()
                if v["mc_username"].lower() != mc_username.lower()
            }

            data[str(discord_id)] = {
                "mc_username":     mc_username,
                "is_premium":      is_premium,
                "linked_at":       datetime.now(timezone.utc).isoformat(),
                "last_verified":   None,
                "last_disconnect": None,
            }

            await asyncio.to_thread(self._write_sync, data)

    async def unlink_account(self, discord_id: int) -> bool:
        """Remove link. Returns True if something was removed."""
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)
            if str(discord_id) not in data:
                return False
            del data[str(discord_id)]
            await asyncio.to_thread(self._write_sync, data)
            return True

    # ── Session state ─────────────────────────────────────────────────────────

    async def record_verified(self, mc_username: str):
        """
        Called when /verify succeeds.
        Sets last_verified = now, opening the 30-minute grace window.
        """
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)
            import time
            for entry in data.values():
                if entry["mc_username"].lower() == mc_username.lower():
                    entry["last_verified"] = time.time()
                    break
            await asyncio.to_thread(self._write_sync, data)

    async def record_disconnect(self, mc_username: str):
        """
        Called when a player leaves or gets collision-kicked.
        Sets last_disconnect = now. Does NOT reset grace window.
        """
        async with self.lock:
            data = await asyncio.to_thread(self._read_sync)
            import time
            for entry in data.values():
                if entry["mc_username"].lower() == mc_username.lower():
                    entry["last_disconnect"] = time.time()
                    break
            await asyncio.to_thread(self._write_sync, data)

    async def grant_emergency_grace(self, mc_username: str):
        """
        Called on collision — the real player was kicked unfairly by an impersonator.
        Sets last_verified = now so they can reconnect immediately without /verify.
        """
        await self.record_verified(mc_username)

    async def is_within_grace(self, mc_username: str) -> bool:
        """
        Returns True if the player successfully verified within the last GRACE_SECONDS (30 min).
        Grace window is based on last_verified, NOT last_disconnect.
        """
        import time
        data = await self._read()
        for entry in data.values():
            if entry["mc_username"].lower() == mc_username.lower():
                lv = entry.get("last_verified")
                if lv is None:
                    return False
                return (time.time() - lv) <= GRACE_SECONDS
        return False
```

---

## File 2 — `src/join_guard.py` (FULL REPLACE)

```python
import asyncio
import secrets
import time
import discord
from src.mc_link_manager import MCLinkManager
from src.mojang import verify_premium_mc_account
from src.logger import logger
from src.utils import rcon_cmd

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

CHALLENGE_TIMEOUT  = 5 * 60   # 5 minutes — how long a /verify code stays valid
COOLDOWN_SECONDS   = 60       # 60 seconds — minimum gap between two challenges for same username
CODE_ALPHABET      = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I (visually confusing)
CODE_LENGTH        = 6        # 34^6 ≈ 1.6 billion combinations


class JoinGuard:
    """
    Security gatekeeper for offline-mode Minecraft servers.

    Decision tree on every login:

    1. Premium account (Mojang API confirms)  → ALLOW silently
    2. Not in mc_links.json                   → KICK with /link instructions
    3. Within 30-minute grace window          → ALLOW silently
    4. Within 60-second anti-spam cooldown    → IGNORE silently (no kick, no log spam)
    5. Otherwise                              → KICK with 6-char code in kick reason
                                                Player uses /verify <code> in Discord #commands
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.link_manager = MCLinkManager()

        # username.lower() → { discord_id, code, expires_at }
        self.active_challenges: dict[str, dict] = {}

        # username.lower() → unix timestamp of last kick (anti-spam)
        self._kick_cooldowns: dict[str, float] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry points (called from bot event dispatchers in bot.py)
    # ──────────────────────────────────────────────────────────────────────────

    async def handle_player_login(self, mc_username: str, mc_uuid: str):
        """
        Called by LogWatcher when 'UUID of player X is ...' appears in the log.
        Runs the full decision tree.
        """
        key = mc_username.lower()
        logger.info(f"JoinGuard: login event for {mc_username}")

        # Step 1: Premium check
        is_premium = await verify_premium_mc_account(mc_username)
        if is_premium:
            logger.info(f"JoinGuard: {mc_username} is premium — allow")
            return

        # Step 2: Link check
        link = await self.link_manager.get_link_by_mc(mc_username)
        if not link:
            logger.warning(f"JoinGuard: {mc_username} has no Discord link — kicking")
            await self._kick(
                mc_username,
                "Tvoj Minecraft racun ni povezan z Discordom. "
                "Pridruzis se Discord streznika in vtipkaj /link."
            )
            return

        # Step 3: Grace window (30 min from last /verify)
        if await self.link_manager.is_within_grace(mc_username):
            logger.info(f"JoinGuard: {mc_username} is within grace window — allow")
            return

        # Step 4: Anti-spam cooldown
        last_kick = self._kick_cooldowns.get(key, 0)
        if time.time() - last_kick < COOLDOWN_SECONDS:
            logger.debug(f"JoinGuard: {mc_username} on cooldown — ignoring join silently")
            return

        # Step 5: Issue challenge
        logger.info(f"JoinGuard: issuing challenge for {mc_username}")
        await self._issue_challenge(mc_username, link["discord_id"])

    def handle_player_quit(self, mc_username: str):
        """
        Called by LogWatcher when 'X left the game' appears.
        Records disconnect timestamp.
        Does NOT clear active challenge — it stays valid for its remaining window.
        Does NOT reset grace window — grace is based on last_verified, not last_disconnect.
        """
        asyncio.create_task(self.link_manager.record_disconnect(mc_username))
        logger.debug(f"JoinGuard: recorded disconnect for {mc_username}")

    async def handle_collision(self, mc_username: str):
        """
        Called when 'X lost connection: You logged in from another location' appears.
        The real player was kicked unfairly by an impersonator.
        1. Grant emergency grace so real player can reconnect immediately without /verify.
        2. Send DM alert to the real player's Discord account.
        """
        await self.link_manager.grant_emergency_grace(mc_username)
        logger.warning(f"JoinGuard: collision detected for {mc_username}")

        link = await self.link_manager.get_link_by_mc(mc_username)
        if not link:
            return

        try:
            user = self.bot.get_user(link["discord_id"]) or \
                   await self.bot.fetch_user(link["discord_id"])

            embed = discord.Embed(
                title="Poskus laznega predstavljanja!",
                description=(
                    f"Nekdo se je prilogiral na streznik kot **{mc_username}** "
                    f"medtem ko si bil ti v igri in te je kicknil.\n\n"
                    f"Tvoj racun ima odprt **30-minutni dostop** — reconnectaj se takoj.\n\n"
                    f"Ce nisi ti, sporoci administratorju."
                ),
                color=discord.Color.red()
            )
            await user.send(embed=embed)
            logger.info(f"JoinGuard: collision DM sent to {user.name}")

        except Exception as e:
            logger.error(f"JoinGuard: failed to send collision DM for {mc_username}: {e}")

    async def complete_challenge(self, mc_username: str):
        """
        Called when /verify succeeds.
        Clears the active challenge and opens the 30-minute grace window.
        """
        key = mc_username.lower()
        if key in self.active_challenges:
            del self.active_challenges[key]
        await self.link_manager.record_verified(mc_username)
        logger.info(f"JoinGuard: challenge completed for {mc_username} — grace window opened")

    # ──────────────────────────────────────────────────────────────────────────
    # /verify logic — called from cogs/link.py
    # ──────────────────────────────────────────────────────────────────────────

    async def verify_code(self, discord_id: int, code: str) -> tuple[bool, str]:
        """
        Attempt to verify a code submitted via /verify.
        Returns (success: bool, message: str).
        Message is shown to the user as ephemeral response.
        """
        code = code.upper().strip()

        for mc_username, challenge in list(self.active_challenges.items()):
            if challenge["discord_id"] != discord_id:
                continue

            # Found a challenge owned by this Discord user
            if time.time() > challenge["expires_at"]:
                del self.active_challenges[mc_username]
                return False, (
                    "Koda je potekla. Prilogiras se na streznik znova in dobit bos novo kodo."
                )

            if challenge["code"] != code:
                return False, "Napacna koda. Preveri kick reason in poskusi znova."

            # Correct and within time
            await self.complete_challenge(mc_username)
            return True, (
                f"Identiteta potrjena! Imas **30 minut** da se prilogiras kot **{mc_username}**."
            )

        return False, (
            "Ni aktivnega izziva za tvoj racun. "
            "Prilogiras se na streznik najprej, nato vtipkaj kodo ki jo dobis na kick screenu."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_code(self) -> str:
        """Generate a cryptographically secure 6-character alphanumeric code."""
        return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))

    async def _issue_challenge(self, mc_username: str, discord_id: int):
        """
        Kick the player and store the active challenge.
        Code appears in the kick reason only — no DMs sent here.
        """
        key = mc_username.lower()
        code = self._generate_code()
        expires_at = time.time() + CHALLENGE_TIMEOUT

        # Cancel previous challenge for this username if any
        self.active_challenges.pop(key, None)

        # Store new challenge
        self.active_challenges[key] = {
            "discord_id": discord_id,
            "code":        code,
            "expires_at":  expires_at,
        }

        # Record cooldown timestamp
        self._kick_cooldowns[key] = time.time()

        # Schedule expiry cleanup
        asyncio.create_task(self._expire_challenge(key, expires_at))

        # Kick with code in reason
        reason = (
            f"Verifikacija potrebna! "
            f"Koda: {code} "
            f"V Discordu vtipkaj v #commands: "
            f"/verify {code} "
            f"Imas 5 minut."
        )
        await self._kick(mc_username, reason)

    async def _expire_challenge(self, key: str, expires_at: float):
        """Remove challenge from memory after it expires."""
        await asyncio.sleep(CHALLENGE_TIMEOUT + 5)
        challenge = self.active_challenges.get(key)
        if challenge and challenge["expires_at"] == expires_at:
            del self.active_challenges[key]
            logger.debug(f"JoinGuard: challenge expired for {key}")

    async def _kick(self, mc_username: str, reason: str):
        """Kick a player via RCON. Waits 1 second to ensure player is fully connected."""
        await asyncio.sleep(1.0)
        # Escape quotes and collapse newlines (RCON kick reason is single-line)
        escaped = reason.replace('"', '\\"').replace("\n", " | ")
        try:
            await rcon_cmd(f'kick {mc_username} "{escaped}"')
            logger.info(f"JoinGuard: kicked {mc_username}")
        except Exception as e:
            logger.error(f"JoinGuard: failed to kick {mc_username}: {e}")
```

---

## File 3 — `cogs/link.py` (FULL REPLACE)

```python
import discord
from discord import app_commands
from discord.ext import commands
from src.mc_link_manager import MCLinkManager
from src.mojang import verify_premium_mc_account
from src.logger import logger
from src.utils import has_role


class Link(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.link_manager = MCLinkManager()

    # ── /link ─────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="link",
        description="Povezi svoj Discord racun z Minecraft uporabniskim imenom"
    )
    @app_commands.describe(username="Tvoje tocno Minecraft uporabnisko ime")
    async def link_cmd(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            existing = await self.link_manager.get_link_by_mc(username)
            if existing and existing["discord_id"] != interaction.user.id:
                await interaction.followup.send(
                    f"Uporabnisko ime **{username}** je ze povezano z drugim Discord racunom. "
                    "Ce gre za napako, kontaktiraj admina.",
                    ephemeral=True
                )
                return

            current = await self.link_manager.get_link_by_discord(interaction.user.id)
            replacement_notice = ""
            if current:
                old_name = current["mc_username"]
                if old_name.lower() == username.lower():
                    await interaction.followup.send(
                        f"Tvoj racun je ze povezan z **{username}**.",
                        ephemeral=True
                    )
                    return
                replacement_notice = f"\n*(Zamenjuje prejsnjo povezavo z **{old_name}**)*"

            is_premium = await verify_premium_mc_account(username)
            await self.link_manager.link_account(interaction.user.id, username, is_premium)

            if is_premium:
                status = (
                    "Premium racun zaznan. "
                    "Mojang API je potrdil tvojo identiteto — verifikacijska koda ni potrebna."
                )
            else:
                status = (
                    "Cracked / offline racun zaznan. "
                    "Ko se prilogis po vec kot 30 minutah odsotnosti, bos dobil kodo "
                    "na kick screenu. Vtipkaj /verify <koda> v #commands."
                )

            await interaction.followup.send(
                f"Discord uspesno povezan z Minecraft racunom **{username}**.\n\n"
                f"{status}{replacement_notice}",
                ephemeral=True
            )
            logger.info(f"{interaction.user.name} linked MC account {username} (premium={is_premium})")

        except Exception as e:
            logger.error(f"Error in /link: {e}", exc_info=True)
            await interaction.followup.send("Nepricakovana napaka. Preveri bot loge.", ephemeral=True)

    # ── /verify ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="verify",
        description="Potrdi svojo identiteto z verifikacijsko kodo (dobis jo na kick screenu)"
    )
    @app_commands.describe(code="6-znakovna koda iz kick sporocila")
    async def verify_cmd(self, interaction: discord.Interaction, code: str):
        guard = self.bot.join_guard

        if not guard:
            await interaction.response.send_message(
                "JoinGuard ni aktiven. Kontaktiraj admina.",
                ephemeral=True
            )
            return

        success, message = await guard.verify_code(interaction.user.id, code)
        await interaction.response.send_message(message, ephemeral=True)

    # ── /unlink ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="unlink",
        description="Odstrani povezavo med tvojim Discord in Minecraft racunom"
    )
    async def unlink_cmd(self, interaction: discord.Interaction):
        success = await self.link_manager.unlink_account(interaction.user.id)
        if success:
            await interaction.response.send_message(
                "Minecraft racun uspesno odklenjen.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Nimas povezanega Minecraft racuna.", ephemeral=True
            )

    # ── /linked ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="linked",
        description="Preveri katero Minecraft ime je povezano s tvojim Discord racunom"
    )
    async def linked_cmd(self, interaction: discord.Interaction):
        entry = await self.link_manager.get_link_by_discord(interaction.user.id)
        if not entry:
            await interaction.response.send_message(
                "Nimas povezanega Minecraft racuna. Uporabi /link <username>.",
                ephemeral=True
            )
            return

        import time
        grace_remaining = ""
        lv = entry.get("last_verified")
        if lv:
            remaining = (lv + 1800) - time.time()
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                grace_remaining = f"\nGrace window: se **{mins}m {secs}s**"

        account_type = "Premium" if entry.get("is_premium") else "Cracked/Offline"

        await interaction.response.send_message(
            f"**Minecraft racun:** `{entry['mc_username']}`\n"
            f"**Tip racuna:** {account_type}"
            f"{grace_remaining}",
            ephemeral=True
        )

    # ── /unlink_admin ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="unlink_admin",
        description="[Admin] Prisilno odstrani Discord-MC povezavo"
    )
    @app_commands.describe(
        discord_user="Discord uporabnik katerega povezavo zelis odstraniti",
        mc_username="ALI Minecraft uporabnisko ime"
    )
    @has_role("cmd")
    async def unlink_admin_cmd(
        self,
        interaction: discord.Interaction,
        discord_user: discord.Member | None = None,
        mc_username: str | None = None
    ):
        if not discord_user and not mc_username:
            await interaction.response.send_message(
                "Podaj Discord uporabnika ALI Minecraft username.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        target_id = None
        if discord_user:
            target_id = discord_user.id
        elif mc_username:
            link = await self.link_manager.get_link_by_mc(mc_username)
            if link:
                target_id = link["discord_id"]

        if target_id:
            success = await self.link_manager.unlink_account(target_id)
            if success:
                await interaction.followup.send("Povezava uspesno odstranjena.", ephemeral=True)
            else:
                await interaction.followup.send("Zapis ne obstaja.", ephemeral=True)
        else:
            await interaction.followup.send("Ni najden noben zapis za ta vhod.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Link(bot))
```

---

## File 4 — `src/utils_views.py` (DELETE)

Delete this file entirely. It contained `ChallengeView` and `CodeModal` for the old DM-button flow.
Nothing in the new implementation imports from it.

After deleting, search the entire codebase for any remaining import of `utils_views` and remove those import lines.

---

## File 5 — `bot.py` — two small changes required

### Change 1: Remove `utils_views` import if present

Find and remove any line like:
```python
from src.utils_views import ChallengeView
```

### Change 2: Ensure `bot.join_guard` is set before `on_ready` syncs commands

In `MinecraftBot.__init__`, the `JoinGuard` is already instantiated as `self.join_guard`.
Verify that this line exists and uses the new constructor signature (only `bot`, no `rcon` or `log_path` args):

```python
self.join_guard = JoinGuard(self)
```

If the existing line passes extra arguments (`rcon=`, `log_path=`, `exempt_usernames=`), remove those arguments. The new `JoinGuard.__init__` only takes `bot`.

---

## File 6 — `data/user_config.json` — permissions update

Add `"verify"` and `"link"` and `"linked"` and `"unlink"` to the `"@everyone"` permission list if not already present. Every player must be able to run these commands.

```json
"@everyone": [
    "status", "players", "seed", "version", "info", "mods", "help",
    "link", "unlink", "linked", "verify"
]
```

---

## File 7 — `src/log_watcher.py` — verify dispatch calls

Open this file and verify that all three dispatch calls exist. If any are missing, add them.

Required dispatches:

```python
# On login line match:
self.bot.dispatch('minecraft_player_login', username, uuid)

# On leave line match:
self.bot.dispatch('minecraft_player_quit', username)

# On collision line match ("lost connection: You logged in from another location"):
self.bot.dispatch('minecraft_collision', username)
```

### Required regex patterns (verify these exist or add them):

```python
# Login: fires before player is fully in-game — used for JoinGuard
auth_pattern = re.compile(
    r'\[(?:[0-9:]+)\] \[User Authenticator #\d+/INFO\].*?UUID of player (?P<username>[A-Za-z0-9_]+) is (?P<uuid>[0-9a-fA-F-]+)'
)

# Leave
leave_pattern = re.compile(
    r'\[(?:[0-9:]+)\] \[Server thread/INFO\].*?(?P<username>[A-Za-z0-9_]+) left the game'
)

# Collision (impersonation detection)
collision_pattern = re.compile(
    r'\[(?:[0-9:]+)\] \[.*?/INFO\].*?(?P<username>[A-Za-z0-9_]+) lost connection: You logged in from another location'
)
```

---

## File 8 — `bot.py` — wire up the new event listeners

In `MinecraftBot.__init__` or `setup_hook`, verify these three listeners are registered:

```python
self.add_listener(self.on_minecraft_player_login,  'on_minecraft_player_login')
self.add_listener(self.on_minecraft_player_quit,   'on_minecraft_player_quit')
self.add_listener(self.on_minecraft_collision,     'on_minecraft_collision')
```

Add the handler methods to `MinecraftBot` if missing:

```python
async def on_minecraft_player_login(self, username: str, uuid: str):
    await self.join_guard.handle_player_login(username, uuid)

async def on_minecraft_player_quit(self, username: str):
    self.join_guard.handle_player_quit(username)

async def on_minecraft_collision(self, username: str):
    await self.join_guard.handle_collision(username)
```

Note: `handle_player_quit` is synchronous (creates a task internally), so no `await` needed.

---

## Deployment checklist — verify before calling done

- [ ] `src/utils_views.py` deleted, all imports of it removed
- [ ] `JoinGuard(self)` constructor takes only `bot` — no extra args
- [ ] `bot.join_guard` is set in `MinecraftBot.__init__`
- [ ] Three event listeners registered in `bot.py`
- [ ] `/verify` and `/link` are in `@everyone` permissions in `user_config.json`
- [ ] `log_watcher.py` dispatches all three events: login, quit, collision
- [ ] No remaining references to `ChallengeView`, `CodeModal`, or `handle_reaction`
- [ ] `data/mc_links.json` schema is compatible — existing records missing `last_verified`/`last_disconnect` fields will have them as `None` which is handled correctly by `is_within_grace()`

---

## Constants reference

```
GRACE_SECONDS     = 1800   (30 min) — in mc_link_manager.py
CHALLENGE_TIMEOUT = 300    (5 min)  — in join_guard.py
COOLDOWN_SECONDS  = 60     (60 sec) — in join_guard.py
CODE_ALPHABET     = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH       = 6
```

---

## Security properties this implementation provides

| Attack | Result |
|--------|--------|
| Attacker knows username, tries to join | Kicked — code shown only on attacker's own kick screen, useless without victim's Discord |
| Attacker spam joins | 60s cooldown — silently ignored after first kick |
| Attacker joins while real player is online | Real player gets DM alert + emergency grace. Attacker gets kicked with a code only usable from victim's Discord account |
| Attacker joins within 30 min of victim's last /verify | Grace window is tied to discord_id that ran /verify — attacker cannot inherit it |
| Mojang API outage | Fail-open — all players treated as premium, nobody blocked |
| Player has DMs disabled | No issue — code is on kick screen, DMs only used for collision alerts |
| /verify from wrong Discord account | `verify_code` checks discord_id — only the linked account can verify |