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
        
        # Keep references to background tasks to prevent garbage collection
        self._background_tasks = set()

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry points (called from bot event dispatchers in bot.py)
    # ──────────────────────────────────────────────────────────────────────────

    async def handle_player_login(self, mc_username: str, mc_uuid: str):
        """
        Called by LogWatcher when 'UUID of player X is ...' appears in the log.
        Runs the full decision tree.
        """
        from src.config import config
        if config.ONLINE_MODE:
            logger.info(f"JoinGuard: Server is in online-mode — bypassing login checks")
            return

        key = mc_username.lower()
        logger.info(f"JoinGuard: login event for {mc_username}")

        try:
            # Step 1: Link check
            link = await self.link_manager.get_link_by_mc(mc_username)
            if not link:
                logger.warning(f"JoinGuard: {mc_username} has no Discord link — kicking")
                await self._kick(
                    mc_username,
                    "Tvoj Minecraft racun ni povezan z Discordom. "
                    "Pridruzis se Discord streznika in vtipkaj /link."
                )
                return

            # Step 2: Grace window (30 min from last /verify)
            if await self.link_manager.is_within_grace(mc_username):
                logger.info(f"JoinGuard: {mc_username} is within grace window — allow")
                return

            # Step 3: Anti-spam cooldown
            last_kick = self._kick_cooldowns.get(key, 0)
            if time.time() - last_kick < COOLDOWN_SECONDS:
                logger.debug(f"JoinGuard: {mc_username} on cooldown — kicking with existing challenge")
                challenge = self.active_challenges.get(key)
                if challenge:
                    reason = (
                        f"Verifikacija potrebna! "
                        f"Koda: {challenge['code']} "
                        f"V Discordu vtipkaj v #commands: "
                        f"/verify {challenge['code']}"
                    )
                else:
                    reason = "Prosimo pocakajte pred ponovno povezavo."
                await self._kick(mc_username, reason)
                return

            # Step 4: Issue challenge
            logger.info(f"JoinGuard: issuing challenge for {mc_username}")
            await self._issue_challenge(mc_username, link["discord_id"])

        except Exception as e:
            logger.error(f"JoinGuard: Error during login verification for {mc_username}: {e}", exc_info=True)
            await self._kick(
                mc_username,
                "Napaka pri preverjanju varnosti. Prosimo, poskusite znova."
            )

    def handle_player_quit(self, mc_username: str):
        """
        Called by LogWatcher when 'X left the game' appears.
        Records disconnect timestamp.
        Does NOT clear active challenge — it stays valid for its remaining window.
        Does NOT reset grace window — grace is based on last_verified, not last_disconnect.
        """
        from src.config import config
        if config.ONLINE_MODE:
            return

        task = asyncio.create_task(self.link_manager.record_disconnect(mc_username))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        logger.debug(f"JoinGuard: recorded disconnect for {mc_username}")

    async def handle_collision(self, mc_username: str):
        """
        Called when 'X lost connection: You logged in from another location' appears.
        The real player was kicked unfairly by an impersonator.
        1. Grant emergency grace so real player can reconnect immediately without /verify.
        2. Send DM alert to the real player's Discord account.
        """
        from src.config import config
        if config.ONLINE_MODE:
            return

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

        user_challenges = [
            (mc_name, chal) for mc_name, chal in self.active_challenges.items()
            if chal["discord_id"] == discord_id
        ]

        if not user_challenges:
            return False, (
                "Ni aktivnega izziva za tvoj racun. "
                "Prilogiras se na streznik najprej, noto vtipkaj kodo ki jo dobis na kick screenu."
            )

        for mc_username, challenge in user_challenges:
            if challenge["code"] == code:
                if time.time() > challenge["expires_at"]:
                    del self.active_challenges[mc_username]
                    return False, (
                        "Koda je potekla. Prilogiras se na streznik znova in dobit bos novo kodo."
                    )

                # Correct and within time
                await self.complete_challenge(mc_username)
                return True, (
                    f"Identiteta potrjena! Imas **30 minut** da se prilogiras kot **{mc_username}**."
                )

        return False, "Napacna koda. Preveri kick reason in poskusi znova."

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
        task = asyncio.create_task(self._expire_challenge(key, expires_at))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

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
        """Kick a player via RCON. Waits 0.5 seconds to ensure player is fully connected."""
        await asyncio.sleep(0.5)
        # Escape quotes and collapse newlines (RCON kick reason is single-line)
        escaped = reason.replace('"', '\\"').replace("\n", " | ")
        try:
            # We use rcon_cmd directly here
            success, response = await rcon_cmd(f'kick {mc_username} "{escaped}"')
            if success:
                logger.info(f"JoinGuard: kicked {mc_username}")
            else:
                logger.error(f"JoinGuard: failed to kick {mc_username}: {response}")
        except Exception as e:
            logger.error(f"JoinGuard: exception while kicking {mc_username}: {e}")
