import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.logger import logger
from src.setup_forms import SetupFormView
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
        
        # Show new form-based setup
        embed = discord.Embed(
            title="🔧 Minecraft Server Setup",
            description="Configure your Minecraft server using the dropdowns below.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 Step 1: Select Options",
            value="Choose your platform, version, and difficulty using the dropdowns below.",
            inline=False
        )
        embed.add_field(
            name="📝 Step 2: Basic Settings",
            value="Click 'Continue to Basic Settings' to configure players and RAM.",
            inline=False
        )
        embed.set_footer(text="You can access Advanced Settings at any time")
        
        view = SetupFormView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Setup(bot))