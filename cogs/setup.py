import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.logger import logger
from src.setup_helper import SetupHelper
from src.installer_views import PlatformSelectView, InstallationManager
import json
import os

class Setup(commands.Cog):
    """Discord server setup commands for Minecraft bot"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Set up Discord channels and install Minecraft server")
    async def setup(self, interaction: discord.Interaction):
        """
        Complete setup: Discord structure + Minecraft server installation
        """
        # Check permissions
        if not interaction.user.guild_permissions.administrator and interaction.user != interaction.guild.owner:
            await interaction.response.send_message(
                "❌ You need Administrator permissions to run this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)
        
        # === STEP 1: Discord Structure Setup ===
        embed = discord.Embed(
            title="🔧 Server Setup - Step 1/2",
            description="Setting up Discord structure...",
            color=discord.Color.blue()
        )
        message = await interaction.followup.send(embed=embed)
        
        try:
            # Run Discord setup
            setup_helper = SetupHelper(self.bot)
            updates = await setup_helper.ensure_setup(interaction.guild)
            
            # Update config
            config.update_dynamic_config(updates)
            await self._save_config_to_file(updates)
            
            # Show success
            command_channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
            log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            debug_channel = self.bot.get_channel(config.DEBUG_CHANNEL_ID)
            
            embed.description = (
                "✅ Discord structure created!\n\n"
                f"📁 Category: Minecraft Server\n"
                f"💬 Commands: {command_channel.mention if command_channel else '?'}\n"
                f"📜 Logs: {log_channel.mention if log_channel else '?'}\n"
                f"🐛 Debug: {debug_channel.mention if debug_channel else '?'}"
            )
            await message.edit(embed=embed)
            
            logger.info(f"Discord setup completed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Discord setup failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ Setup failed: {e}"
            await message.edit(embed=embed)
            return
        
        # === STEP 2: Minecraft Server Installation ===
        server_jar = os.path.join(config.SERVER_DIR, "server.jar")
        
        if os.path.exists(server_jar):
            # Server already installed
            embed = discord.Embed(
                title="✅ Setup Complete!",
                description="Discord structure is ready!\n\nℹ️ Minecraft server is already installed.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Quick Start",
                value=f"Use `/start` in {command_channel.mention if command_channel else 'command channel'} to launch the server!",
                inline=False
            )
            await message.edit(embed=embed)
            return
        
        # Start Minecraft installation
        embed = discord.Embed(
            title="🎮 Server Setup - Step 2/2",
            description="Time to install your Minecraft server!\n\nChoose a server platform:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📄 Paper (Recommended)",
            value="Best performance, plugin support",
            inline=True
        )
        embed.add_field(
            name="🧊 Vanilla",
            value="Official Mojang server",
            inline=True
        )
        embed.add_field(
            name="🧵 Fabric",
            value="Mod support, lightweight",
            inline=True
        )
        
        # Create installation manager
        installer_mgr = InstallationManager(interaction, message)
        view = PlatformSelectView(installer_mgr)
        
        await message.edit(embed=embed, view=view)

    async def _save_config_to_file(self, updates: dict):
        """Save configuration updates to config.json file"""
        try:
            with open('config.json', 'r') as f:
                config_data = json.load(f)
            
            if 'command_channel_id' in updates:
                config_data['command_channel_id'] = updates['command_channel_id']
            if 'log_channel_id' in updates:
                config_data['log_channel_id'] = updates['log_channel_id']
            if 'debug_channel_id' in updates:
                config_data['debug_channel_id'] = updates['debug_channel_id']
            if 'roles' in updates:
                config_data['roles'] = updates['roles']
            
            with open('config.json', 'w') as f:
                json.dump(config_data, f, indent='\t')
                f.write('\n')
            
            logger.info("config.json updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update config.json: {e}")
            raise

async def setup(bot):
    await bot.add_cog(Setup(bot))