import asyncio
import time
from src.mc_link_manager import MCLinkManager
from src.mojang import verify_premium_mc_account
from src.logger import logger
from src.utils import rcon_cmd
from src.config import config
import discord

class JoinGuard:
    """
    Manages player login verification and cracked account security.

    Attributes:
        bot (commands.Bot): The Discord bot instance.
        link_manager (MCLinkManager): Manager for Discord-Minecraft account links.
        verified_sessions (dict[str, float]): Tracks timestamps of verified MC UUIDs.
        SESSION_DURATION (int): Time in seconds a verified session lasts.
        active_challenges (dict[str, dict]): Stores details of pending challenges.
    """
    def __init__(self, bot):
        """Initializes the JoinGuard with necessary managers and settings."""
        self.bot = bot
        self.link_manager = MCLinkManager()
        # Dictionary tracking verified sessions: { mc_uuid: verified_timestamp }
        self.verified_sessions: dict[str, float] = {}
        # 30 minutes in seconds
        self.SESSION_DURATION = 1800 
        
        # Active challenges: { mc_username: { "discord_id": int, "timeout_task": Task, "code": str, "attempts": int, "uuid": str } }
        self.active_challenges: dict[str, dict] = {}
        
        # Load persisted sessions
        self._load_sessions()

    def _load_sessions(self):
        """Loads verified_sessions from bot_config.json."""
        try:
            bot_cfg = config.load_bot_config()
            self.verified_sessions = bot_cfg.get('verified_sessions', {})
            # Clean up expired ones on load
            now = time.time()
            self.verified_sessions = {
                u: t for u, t in self.verified_sessions.items() 
                if (now - t) <= self.SESSION_DURATION
            }
        except Exception as e:
            logger.error(f"JoinGuard: Failed to load sessions: {e}")

    def _save_sessions(self):
        """Saves verified_sessions to bot_config.json."""
        try:
            with config.update_bot_config() as bot_cfg:
                bot_cfg['verified_sessions'] = self.verified_sessions
        except Exception as e:
            logger.error(f"JoinGuard: Failed to save sessions: {e}")

    # --- Login/Quit Handlers ---

    async def handle_player_login(self, mc_username: str, mc_uuid: str):
        """
        Processes a player login attempt from the server logs.

        Args:
            mc_username (str): The Minecraft username of the player.
            mc_uuid (str): The Minecraft UUID of the player.
        """
        try:
            logger.info(f"JoinGuard examining login: {mc_username} ({mc_uuid})")
            
            link_info = await self.link_manager.get_link_by_mc(mc_username)
            
            # 1. Unlinked Account Logic
            if not link_info:
                # Security hardening: In offline-mode, Mojang auto-verification is disabled 
                # to prevent "Notch spoofing" bypasses. Everyone must link.
                logger.warning(f"JoinGuard: Unlinked join attempt by {mc_username} ({mc_uuid}). Kicking.")
                await self._kick_player(mc_username, "You must link your Discord account to play! Use /link in our Discord server.")
                return

            # 2. Premium Link Logic
            if link_info.get("is_premium"):
                # We trust this link because it was verified by Mojang API during /link.
                # However, in offline-mode, UUIDs can be spoofed. 
                # If we want maximum security, even premium links should use /verify.
                # For now, we trust the username link if it was established as premium.
                logger.info(f"JoinGuard: Verified premium link for {mc_username}. Allowing join.")
                return

            # 3. Cracked Link Logic
            # Check if this specific UUID has a verified session active
            last_verified = self.verified_sessions.get(mc_uuid)
            now = time.time()
            
            if last_verified and (now - last_verified) <= self.SESSION_DURATION:
                logger.info(f"JoinGuard: Session verified for {mc_username} ({mc_uuid}). Allowing join.")
                return
            
            # No active session. Issue a challenge.
            discord_id = link_info["discord_id"]
            await self._issue_challenge(mc_username, discord_id, mc_uuid)
            
        except Exception as e:
            logger.error(f"JoinGuard Error handling login for {mc_username}: {e}", exc_info=True)

    def grant_session(self, mc_uuid: str):
        """
        Grants a verified session to a UUID.
        """
        self.verified_sessions[mc_uuid] = time.time()
        self._save_sessions()
        logger.debug(f"JoinGuard: Granted session for UUID {mc_uuid}.")

    # --- Challenge Logic ---

    async def _issue_challenge(self, mc_username: str, discord_id: int, mc_uuid: str):
        """
        Kicks the player with a verification code and sends a notification.

        Args:
            mc_username (str): The Minecraft username to verify.
            discord_id (int): The Discord ID of the linked user.
            mc_uuid (str): The UUID of the player connecting.
        """
        import secrets
        import string
        # Generate 6 char alphanumeric code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        
        kick_reason = f"Verification Required. Check Discord. Code: {code}"
        # Immediate kick, no sleep
        await self._kick_player(mc_username, kick_reason)

        # Cancel any existing challenge for this user
        if mc_username in self.active_challenges:
            self.active_challenges[mc_username]["timeout_task"].cancel()

        # Fetch user
        try:
            user = self.bot.get_user(discord_id)
            if not user:
                user = await self.bot.fetch_user(discord_id)
        except Exception as e:
            logger.error(f"JoinGuard: Could not fetch user {discord_id}: {e}")
            return

        embed = discord.Embed(
            title="🔒 Minecraft Login Verification",
            description=f"Someone (hopefully you) is trying to log into the Minecraft server as **{mc_username}**.\n\n"
                        f"Please use the code shown on your Minecraft kick screen with the **`/verify`** command in this Discord server.\n\n"
                        f"*(This code expires in 5 minutes)*",
            color=discord.Color.orange()
        )

        msg = None
        try:
            msg = await user.send(embed=embed)
            logger.info(f"JoinGuard: Sent DM notification to {user.name} for {mc_username}.")
        except discord.Forbidden:
            logger.warning(f"JoinGuard: DMs disabled for {user.name}, falling back to command channel.")
            try:
                channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
                if channel:
                    msg = await channel.send(
                        f"{user.mention} — your DMs are disabled. A login attempt for **{mc_username}** requires verification:",
                        embed=embed
                    )
            except Exception as e:
                logger.error(f"JoinGuard: Failed to send notification to command channel: {e}")
        except Exception as e:
            logger.error(f"JoinGuard: Failed to send DM notification to {discord_id}: {e}")

        if msg is not None:
            timeout_task = asyncio.create_task(self._challenge_timeout(mc_username, msg))
            self.active_challenges[mc_username] = {
                "discord_id": discord_id,
                "code": code,
                "timeout_task": timeout_task,
                "message": msg,
                "attempts": 0,
                "uuid": mc_uuid
            }

    async def complete_challenge(self, mc_username: str):
        """
        Handles successful completion of a verification challenge.

        Args:
            mc_username (str): The Minecraft username that was verified.
        """
        if mc_username in self.active_challenges:
            challenge = self.active_challenges[mc_username]
            challenge["timeout_task"].cancel()
            
            # Grant session to the UUID that triggered this challenge
            mc_uuid = challenge.get("uuid")
            if mc_uuid:
                self.grant_session(mc_uuid)
            
            del self.active_challenges[mc_username]
            logger.info(f"JoinGuard: Challenge completed for {mc_username}. Session granted.")

    async def verify_code(self, discord_id: int, code: str) -> tuple[bool, str]:
        """
        Verifies a code submitted via /verify command.
        """
        code = code.upper().strip()
        
        # 1. Gather all active challenges for this Discord user
        user_challenges = {
            mc: chal for mc, chal in self.active_challenges.items() 
            if chal["discord_id"] == discord_id
        }
        
        if not user_challenges:
            return False, "❌ **No active verification challenge found for your account.** Please try joining the server first."

        # 2. Check if the code matches any of their active challenges
        for mc_username, challenge in user_challenges.items():
            if challenge["code"] == code:
                await self.complete_challenge(mc_username)
                return True, f"✅ **Verification successful for `{mc_username}`.** You may now join the server."

        # 3. If we reach here, the code was incorrect. Increment attempts for all their challenges.
        max_attempts = 3
        failed_too_many_times = False

        for mc_username, challenge in user_challenges.items():
            challenge["attempts"] += 1
            if challenge["attempts"] >= max_attempts:
                # Invalidate this challenge
                challenge["timeout_task"].cancel()
                del self.active_challenges[mc_username]
                failed_too_many_times = True
                
                # Update the original Discord message to show it failed
                try:
                    msg = challenge["message"]
                    embed = msg.embeds[0]
                    embed.description += f"\n\n❌ **Challenge failed due to too many incorrect attempts.**"
                    embed.color = discord.Color.red()
                    asyncio.create_task(msg.edit(embed=embed))
                except Exception:
                    pass

        if failed_too_many_times:
            return False, "❌ **Too many incorrect attempts.** Your login challenge has been cancelled. Please try joining the Minecraft server again to get a new code."
        
        return False, "❌ **Incorrect verification code.** Please check the code on your Minecraft screen and try again."

    async def _challenge_timeout(self, mc_username: str, message: discord.Message):
        """
        Expires a verification challenge after a period of time.

        Args:
            mc_username (str): The Minecraft username associated with the challenge.
            message (discord.Message): The Discord message containing the challenge.
        """
        await asyncio.sleep(300)
        if mc_username in self.active_challenges:
            del self.active_challenges[mc_username]
            
            try:
                embed = message.embeds[0]
                embed.description += "\n\n❌ **This challenge has expired.**"
                embed.color = discord.Color.red()
                await message.edit(embed=embed)
            except discord.HTTPException:
                pass
            logger.info(f"JoinGuard: Challenge expired for {mc_username}.")

    # --- Utility Methods ---

    async def _kick_player(self, username: str, reason: str):
        """
        Kicks a player from the Minecraft server via RCON.

        Args:
            username (str): The Minecraft username of the player to kick.
            reason (str): The reason for the kick.
        """
        # Sanitize inputs for RCON
        clean_username = username.replace('\n', '').replace('\r', '').replace('"', '')
        clean_reason = reason.replace('\n', ' ').replace('\r', '').replace('"', '\\"')
        cmd = f'kick {clean_username} "{clean_reason}"'
        try:
            # Rapid retry logic for RCON kick to mitigate race conditions
            for _ in range(3):
                success, _ = await rcon_cmd(cmd)
                if success:
                    break
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"JoinGuard failed to kick {username}: {e}")
