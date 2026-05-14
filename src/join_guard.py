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
        recently_disconnected (dict[str, float]): Tracks timestamps of player disconnects.
        GRACE_PERIOD (int): Time in seconds allowed for seamless reconnects.
        active_challenges (dict[str, dict]): Stores details of pending DM challenges.
    """
    def __init__(self, bot):
        """Initializes the JoinGuard with necessary managers and settings."""
        self.bot = bot
        self.link_manager = MCLinkManager()
        # Dictionary tracking disconnected users: { mc_username: disconnect_timestamp }
        self.recently_disconnected: dict[str, float] = {}
        # 30 minutes in seconds
        self.GRACE_PERIOD = 1800 
        
        # We need a reference to the active DM challenges
        # { mc_username: { "discord_id": 123, "timeout_task": Task, "code": "ABC123" } }
        self.active_challenges: dict[str, dict] = {}

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
            
            if not link_info:
                # No link exists. Attempt to verify if they are a real premium account.
                is_premium = await verify_premium_mc_account(mc_username)
                if is_premium:
                    logger.info(f"JoinGuard: Auto-verifying {mc_username} as premium account (no discord required).")
                    return # Allow join
                else:
                    logger.warning(f"JoinGuard: Unlinked cracked join attempt by {mc_username}. Kicking.")
                    await self._kick_player(mc_username, "You must link your Discord account! Use /link in our Discord server.")
                    return

            # Link exists. Check if it's a known premium.
            if link_info.get("is_premium"):
                logger.info(f"JoinGuard: Verified premium link for {mc_username}. Allowing join.")
                return

            # Link exists, but it's a cracked account.
            # We must verify their identity. Check grace period.
            last_disconnect = self.recently_disconnected.get(mc_username.lower())
            now = time.time()
            
            if last_disconnect and (now - last_disconnect) <= self.GRACE_PERIOD:
                logger.info(f"JoinGuard: Seamless reconnect for cracked account {mc_username} (within grace period).")
                # Remove from dict so they don't get unlimited grace periods without actually playing
                del self.recently_disconnected[mc_username.lower()]
                return
            
            # Outside grace period. Issue a DM challenge.
            discord_id = link_info["discord_id"]
            await self._issue_challenge(mc_username, discord_id)
            
        except Exception as e:
            logger.error(f"JoinGuard Error handling login for {mc_username}: {e}", exc_info=True)

    def handle_player_quit(self, mc_username: str):
        """
        Records when a player leaves to start their grace period window.

        Args:
            mc_username (str): The Minecraft username of the player.
        """
        self.recently_disconnected[mc_username.lower()] = time.time()
        logger.debug(f"JoinGuard: Started disconnect grace period for {mc_username}.")

    # --- Challenge Logic ---

    async def _issue_challenge(self, mc_username: str, discord_id: int):
        """
        Kicks the player with a verification code and sends a DM challenge.

        Args:
            mc_username (str): The Minecraft username to verify.
            discord_id (int): The Discord ID of the linked user.
        """
        import secrets
        import string
        # Generate 6 char alphanumeric code
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        
        kick_reason = f"Verification Required. Check your Discord DMs or the server Discord channel. Code: {code}"
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
            description=f"Someone (hopefully you) is trying to log into the Minecraft server as **{mc_username}** outside of the grace period.\n\n"
                        f"To verify your identity and allow the connection, please click the button below and enter the code: **`{code}`**\n\n"
                        f"*(This code expires in 5 minutes)*",
            color=discord.Color.orange()
        )

        from src.utils_views import ChallengeView
        view = ChallengeView(self, mc_username, code)

        msg = None
        try:
            msg = await user.send(embed=embed, view=view)
            logger.info(f"JoinGuard: Sent DM challenge to {user.name} for {mc_username}.")
        except discord.Forbidden:
            logger.warning(f"JoinGuard: DMs disabled for {user.name}, falling back to command channel.")
            try:
                channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
                if channel:
                    msg = await channel.send(
                        f"{user.mention} — your DMs are disabled. Verification code for **{mc_username}**:",
                        embed=embed,
                        view=view
                    )
            except Exception as e:
                logger.error(f"JoinGuard: Failed to send challenge to command channel: {e}")
        except Exception as e:
            logger.error(f"JoinGuard: Failed to send DM challenge to {discord_id}: {e}")

        if msg is not None:
            timeout_task = asyncio.create_task(self._challenge_timeout(mc_username, msg, view))
            self.active_challenges[mc_username] = {
                "discord_id": discord_id,
                "code": code,
                "timeout_task": timeout_task,
                "message": msg
            }

    async def complete_challenge(self, mc_username: str):
        """
        Handles successful completion of a verification challenge.

        Args:
            mc_username (str): The Minecraft username that was verified.
        """
        if mc_username in self.active_challenges:
            self.active_challenges[mc_username]["timeout_task"].cancel()
            del self.active_challenges[mc_username]
            # They verified. Start a fresh grace period so they can log right in.
            self.handle_player_quit(mc_username)
            logger.info(f"JoinGuard: Challenge completed for {mc_username}. Granted grace period.")

    async def verify_code(self, discord_id: int, code: str) -> tuple[bool, str]:
        """
        Verifies a code submitted via /verify command.

        Args:
            discord_id (int): The Discord ID of the user submitting the code.
            code (str): The code submitted by the user.

        Returns:
            tuple[bool, str]: A tuple containing (success_flag, result_message).
        """
        code = code.upper().strip()
        for mc_username, challenge in list(self.active_challenges.items()):
            if challenge["discord_id"] == discord_id:
                if challenge["code"] == code:
                    await self.complete_challenge(mc_username)
                    return True, f"✅ **Verification successful for {mc_username}.** You may now join the server."
                else:
                    return False, "❌ **Incorrect verification code.**"
        
        return False, "❌ **No active verification challenge found for your account.**"

    async def _challenge_timeout(self, mc_username: str, message: discord.Message, view):
        """
        Expires a verification challenge after a period of time.

        Args:
            mc_username (str): The Minecraft username associated with the challenge.
            message (discord.Message): The Discord message containing the challenge.
            view (discord.ui.View): The view associated with the challenge message.
        """
        await asyncio.sleep(300)
        if mc_username in self.active_challenges:
            del self.active_challenges[mc_username]
            
            # Disable buttons in DM
            for item in view.children:
                item.disabled = True
            try:
                embed = message.embeds[0]
                embed.description += "\n\n❌ **This challenge has expired.**"
                embed.color = discord.Color.red()
                await message.edit(embed=embed, view=view)
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
        # Wait a brief moment to ensure they are actually connected enough to be kicked
        await asyncio.sleep(1.0) 
        
        # Sanitize inputs for RCON
        clean_username = username.replace('\n', '').replace('\r', '').replace('"', '')
        clean_reason = reason.replace('\n', ' ').replace('\r', '').replace('"', '\\"')
        cmd = f'kick {clean_username} "{clean_reason}"'
        try:
            await rcon_cmd(cmd)
        except Exception as e:
            logger.error(f"JoinGuard failed to kick {username}: {e}")


