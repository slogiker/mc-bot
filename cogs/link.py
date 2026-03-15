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

    @app_commands.command(name="link", description="Link your Minecraft account for security verification")
    @app_commands.describe(username="Your exact Minecraft username")
    async def link_cmd(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            # Check if this MC account is already linked to someone else
            existing_link = await self.link_manager.get_link_by_mc(username)
            if existing_link and existing_link["discord_id"] != interaction.user.id:
                 await interaction.followup.send(f"❌ The username **{username}** is already linked to another Discord account. If this is an error, contact an Admin.", ephemeral=True)
                 return
                 
            # Check if the user already has a link, and notify we are replacing it
            user_link = await self.link_manager.get_link_by_discord(interaction.user.id)
            replacement_notice = ""
            if user_link:
                 old_name = user_link["mc_username"]
                 if old_name.lower() == username.lower():
                      await interaction.followup.send(f"✅ Your account is already linked to **{username}**.", ephemeral=True)
                      return
                 replacement_notice = f"\n*(This replaces your previous link to **{old_name}**)*"

            # Check Mojang API to detect if premium
            is_premium = await verify_premium_mc_account(username)
            
            # Link it
            await self.link_manager.link_account(interaction.user.id, username, is_premium)
            
            status_text = "🟢 **Premium Account Detected**. You do not need to do DM Verifications." if is_premium else "🟡 **Offline-Mode Account Detected**. You will receive Discord DMs to verify your identity if you re-connect after 5 minutes of being offline."
            
            await interaction.followup.send(
                f"✅ Successfully linked Discord to MC Username: **{username}**\n\n{status_text}{replacement_notice}", 
                ephemeral=True
            )
            logger.info(f"User {interaction.user.name} linked MC account {username} (Premium: {is_premium})")

        except Exception as e:
            logger.error(f"Error in /link command: {e}")
            await interaction.followup.send("❌ An unexpected error occurred while linking.", ephemeral=True)

    @app_commands.command(name="unlink", description="Unlink your Minecraft account")
    async def unlink_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success = await self.link_manager.unlink_account(interaction.user.id)
        if success:
             await interaction.followup.send("✅ Successfully unlinked your Minecraft account.", ephemeral=True)
        else:
             await interaction.followup.send("❌ You don't have any linked Minecraft accounts.", ephemeral=True)

    @app_commands.command(name="unlink_admin", description="Forcefully unlink a Discord user or MC username")
    @app_commands.describe(discord_user="The Discord user to unlink", mc_username="OR the MC username to unlink")
    @has_role("cmd") # Assuming 'cmd' is for admins, adjust if needed
    async def unlink_admin_cmd(self, interaction: discord.Interaction, discord_user: discord.Member | None = None, mc_username: str | None = None):
        if not discord_user and not mc_username:
            await interaction.response.send_message("❌ You must provide either a Discord User or an MC Username.", ephemeral=True)
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
                 await interaction.followup.send(f"✅ Successfully forcefully unlinked.", ephemeral=True)
             else:
                 await interaction.followup.send(f"❌ Failed to unlink. No record found.", ephemeral=True)
        else:
             await interaction.followup.send(f"❌ No linked account found for that input.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Link(bot))
