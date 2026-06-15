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

            class WorldManagementView(ui.View):
                def __init__(self, bot):
                    super().__init__(timeout=180)
                    self.bot = bot

                @ui.button(label="Backup & Reset World", style=discord.ButtonStyle.danger, emoji="💾")
                async def backup_reset(self, interaction: discord.Interaction, button: ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    from src.backup_manager import backup_manager

                    # 1. Create backup
                    await interaction.followup.send("⏳ Creating emergency backup...", ephemeral=True)
                    date_str = discord.utils.utcnow().strftime('%Y-%m-%d_%H-%M')
                    success, filename, path = await backup_manager.create_backup(custom_name=f"setup_reset_{date_str}")

                    if success:
                        await interaction.followup.send(f"✅ Backup created: `{filename}`", ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ Backup failed: {filename}. Proceeding anyway...", ephemeral=True)

                    # 2. Delete world
                    import shutil
                    world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
                    if os.path.exists(world_path):
                        await asyncio.to_thread(shutil.rmtree, world_path)

                    # 3. Proceed to setup
                    from src.setup_views import SetupView
                    view = SetupView(interaction)
                    await view.start()

                @ui.button(label="Reset World (No Backup)", style=discord.ButtonStyle.secondary, emoji="🗑️")
                async def reset_only(self, interaction: discord.Interaction, button: ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    # 1. Delete world
                    import shutil
                    world_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER)
                    if os.path.exists(world_path):
                        await asyncio.to_thread(shutil.rmtree, world_path)

                    # 2. Proceed to setup
                    from src.setup_views import SetupView
                    view = SetupView(interaction)
                    await view.start()

                @ui.button(label="Keep Existing World", style=discord.ButtonStyle.success, emoji="🌍")
                async def keep_world(self, interaction: discord.Interaction, button: ui.Button):
                    await interaction.response.defer(ephemeral=True)
                    await interaction.followup.send(
                        "✅ Keeping world files. You can always restart fresh later if you change your mind.", 
                        ephemeral=True
                    )
                    # Proceed to setup
                    from src.setup_views import SetupView
                    view = SetupView(interaction)
                    await view.start()

                @ui.button(label="Cancel Setup", style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: ui.Button):
                    await interaction.response.send_message("Setup cancelled.", ephemeral=True)

            await interaction.response.send_message(embed=embed, view=WorldManagementView(self.bot), ephemeral=True)
            return

        # Show modern interactive setup view
        view = SetupView(interaction)
        await view.start()
    



async def setup(bot):
    await bot.add_cog(Setup(bot))