import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.setup_views import SetupView, fetch_versions
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

        # Pre-fetch versions for dropdown
        await fetch_versions()

        # Check if server is already installed
        server_jar = os.path.join(config.SERVER_DIR, "server.jar")
        world_folder = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
        
        # We only consider it "already installed" if both the JAR and WORLD exist.
        # If the JAR exists but no WORLD, it might be a broken installation that needs repair.
        if os.path.exists(server_jar) and os.path.exists(world_folder):
            # Server already installed - warn user and handle world management
            embed = discord.Embed(
                title="⚠️ Server Already Installed",
                description="**Running setup again will overwrite your current configuration!**\n\nHow would you like to handle your current world?",
                color=discord.Color.yellow()
            )

            from src.setup_views import WorldManagementView
            await interaction.response.send_message(embed=embed, view=WorldManagementView(self.bot, interaction), ephemeral=True)
            return

        # Show modern interactive setup view
        view = SetupView(interaction)
        await view.start()
    



async def setup(bot):
    await bot.add_cog(Setup(bot))