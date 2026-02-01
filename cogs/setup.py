import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.logger import logger
from src.setup_views import SetupView
from src.mc_installer import mc_installer
import os

class Setup(commands.Cog):
    """Discord server setup commands for Minecraft bot"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Set up Discord channels and install Minecraft server")
    async def setup(self, interaction: discord.Interaction):
        """
        Modern form-based setup with dropdowns and smart defaults
        """
        # Check permissions
        if not interaction.user.guild_permissions.administrator and interaction.user != interaction.guild.owner:
            await interaction.response.send_message(
                "❌ You need Administrator permissions to run this command.",
                ephemeral=True
            )
            return

        # Check if server is already installed
        server_jar = os.path.join(config.SERVER_DIR, "server.jar")
        
        if os.path.exists(server_jar):
            # Server already installed - just show info
            embed = discord.Embed(
                title="ℹ️ Server Already Installed",
                description="Your Minecraft server is already set up!",
                color=discord.Color.blue()
            )
            
            command_channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
            
            embed.add_field(
                name="Quick Start",
                value=f"Use `/start` in {command_channel.mention if command_channel else 'command channel'} to launch the server!",
                inline=False
            )
            
            embed.add_field(
                name="Need to Reinstall?",
                value="1. Stop the server with `/stop`\n2. Backup your world\n3. Delete `mc-server/server.jar`\n4. Run `/setup` again",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Show modern interactive setup view
        view = SetupView(interaction)
        await view.start()
    
    @app_commands.command(name="version", description="Set Minecraft version for setup")
    @app_commands.describe(version="Minecraft version to use")
    async def set_version(self, interaction: discord.Interaction, version: str):
        """Set the Minecraft version (used during setup)"""
        await interaction.response.send_message(
            f"✅ Version set to: {version}\n(This will be used in the next setup)",
            ephemeral=True
        )
    
    @set_version.autocomplete('version')
    async def version_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for Minecraft versions"""
        try:
            # Get platform from current setup state if available
            # For now, default to paper
            platform = "paper"
            
            # Fetch recent versions (this is a simplified version)
            # In production, you'd cache this and fetch from the API
            versions = await self._get_recent_versions(platform)
            
            # Filter based on current input
            if current:
                filtered = [v for v in versions if current.lower() in v.lower()]
            else:
                filtered = versions[:25]  # Discord limit
            
            return [
                app_commands.Choice(name=version, value=version)
                for version in filtered[:25]
            ]
        except Exception as e:
            logger.error(f"Version autocomplete error: {e}")
            return [app_commands.Choice(name="latest", value="latest")]
    
    async def _get_recent_versions(self, platform: str) -> list[str]:
        """Get recent Minecraft versions for a platform"""
        try:
            if platform == "paper":
                # Fetch from Paper API
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.papermc.io/v2/projects/paper") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            versions = data.get("versions", [])
                            # Return latest 25 versions in reverse order (newest first)
                            return ["latest"] + list(reversed(versions[-25:]))
            elif platform == "vanilla":
                # For vanilla, we'd need to fetch from Mojang API
                # Simplified for now
                return ["latest", "1.21.5", "1.21.4", "1.21.3", "1.21.2", "1.21.1", "1.21", "1.20.6", "1.20.5", "1.20.4"]
            else:  # fabric
                return ["latest", "1.21.5", "1.21.4", "1.21.3", "1.21.2", "1.21.1", "1.21", "1.20.6", "1.20.5", "1.20.4"]
        except Exception as e:
            logger.error(f"Failed to fetch versions: {e}")
            return ["latest"]


async def setup(bot):
    await bot.add_cog(Setup(bot))