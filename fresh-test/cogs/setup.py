import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.logger import logger
from src.setup_views import SetupView, fetch_versions
from discord import ui
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

        # Pre-fetch versions for dropdown
        await fetch_versions()

        # Check if server is already installed
        server_jar = os.path.join(config.SERVER_DIR, "server.jar")
        
        if os.path.exists(server_jar):
            # Server already installed - warn user
            embed = discord.Embed(
                title="⚠️ Server Already Installed",
                description="**Running setup again will DELETE the current server!**\n\nThe world will be backed up, but all other files will be removed.",
                color=discord.Color.yellow()
            )
            
            view = ui.View()
            
            async def confirm_callback(interaction: discord.Interaction):
                # Show modern interactive setup view
                view = SetupView(interaction)
                await view.start()
                
            async def cancel_callback(interaction: discord.Interaction):
                await interaction.response.send_message("Setup cancelled.", ephemeral=True)
                
            confirm_btn = ui.Button(label="Yes, Reinstall", style=discord.ButtonStyle.danger, emoji="🗑️")
            confirm_btn.callback = confirm_callback
            
            cancel_btn = ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            cancel_btn.callback = cancel_callback
            
            view.add_item(confirm_btn)
            view.add_item(cancel_btn)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return
        
        # Show modern interactive setup view
        view = SetupView(interaction)
        await view.start()
    



async def setup(bot):
    await bot.add_cog(Setup(bot))