import asyncio
import time
from src.mc_link_manager import MCLinkManager
from src.mojang import verify_premium_mc_account
from src.logger import logger
from src.utils import rcon_cmd
import discord

class JoinGuard:
    def __init__(self, bot):
        self.bot = bot
        self.link_manager = MCLinkManager()
        # Dictionary tracking disconnected users: { mc_username: disconnect_timestamp }
        self.recently_disconnected: dict[str, float] = {}
        # 5 minutes in seconds
        self.GRACE_PERIOD = 300 
        
        # We need a reference to the active DM challenges
        # { mc_username: { "discord_id": 123, "timeout_task": Task, "code": "1234" } }
        self.active_challenges: dict[str, dict] = {}

    async def handle_player_login(self, mc_username: str, mc_uuid: str):
        """Called when a 'User Authenticator' message appears in logs."""
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
        """Record when a player leaves to start their grace window."""
        self.recently_disconnected[mc_username.lower()] = time.time()
        logger.debug(f"JoinGuard: Started disconnect grace period for {mc_username}.")

    async def _issue_challenge(self, mc_username: str, discord_id: int):
        """Kicks the player with a code, slides into their DMs."""
        import random
        # Generate 4 digit code
        code = str(random.randint(1000, 9999))
        
        # Kick player with instructions
        kick_reason = f"Verification Required. Check your Discord DMs.\nCode: {code}"
        await self._kick_player(mc_username, kick_reason)
        
        # Cancel any existing challenge for this user
        if mc_username in self.active_challenges:
            self.active_challenges[mc_username]["timeout_task"].cancel()
            
        # Send DM
        try:
            # We have to fetch the user if they're not cached
            user = self.bot.get_user(discord_id)
            if not user:
                user = await self.bot.fetch_user(discord_id)
                
            embed = discord.Embed(
                title="🔒 Minecraft Login Verification",
                description=f"Someone (hopefully you) is trying to log into the Minecraft server as **{mc_username}** outside of the grace period.\n\n"
                            f"To verify your identity and allow the connection, please click the button below and enter the code: **`{code}`**\n\n"
                            f"*(This code expires in 2 minutes)*",
                color=discord.Color.orange()
            )
            
            # Note: We need to register a persistent view/button somewhere to listen to this.
            # For simplicity, we can do a command-based challenge or a View. Let's do a View.
            from src.utils_views import ChallengeView 
            
            view = ChallengeView(self, mc_username, code)
            msg = await user.send(embed=embed, view=view)
            
            # Setup timeout
            timeout_task = asyncio.create_task(self._challenge_timeout(mc_username, msg, view))
            
            self.active_challenges[mc_username] = {
                "discord_id": discord_id,
                "code": code,
                "timeout_task": timeout_task,
                "message": msg
            }
            logger.info(f"JoinGuard: Sent DM challenge to {user.name} for {mc_username}.")
        except Exception as e:
            logger.error(f"JoinGuard: Failed to send DM challenge to {discord_id}: {e}")

    async def complete_challenge(self, mc_username: str):
        """Called when a user successfully answers the interactive DM."""
        if mc_username in self.active_challenges:
            self.active_challenges[mc_username]["timeout_task"].cancel()
            del self.active_challenges[mc_username]
            # They verified. Start a fresh 5 minute grace period so they can log right in.
            self.handle_player_quit(mc_username)
            logger.info(f"JoinGuard: Challenge completed for {mc_username}. Granted grace period.")

    async def _challenge_timeout(self, mc_username: str, message: discord.Message, view):
        """Expires the challenge after 2 minutes."""
        await asyncio.sleep(120)
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

    async def _kick_player(self, username: str, reason: str):
        """Kicks a player via RCON."""
        # Wait a brief moment to ensure they are actually connected enough to be kicked
        await asyncio.sleep(1.0) 
        
        # Escape quotes in reason
        escaped_reason = reason.replace('"', '\\"')
        cmd = f'kick {username} "{escaped_reason}"'
        try:
            await rcon_cmd(cmd)
        except Exception as e:
            logger.error(f"JoinGuard failed to kick {username}: {e}")

