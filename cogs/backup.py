import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
from src.config import config
from src.logger import logger
from src.backup_manager import backup_manager

class BackupCog(commands.Cog):
    """
    Manages world backups for the Minecraft server.

    Features:
    - Manual backups via /backup.
    - Scheduled backups (daily at configured time).
    - Direct download of backup files.
    """
    def __init__(self, bot):
        """Initializes the BackupCog and starts the backup loop."""
        self.bot = bot
        self.backup_loop.start()

    def cog_unload(self):
        """Cleans up when the cog is unloaded."""
        self.backup_loop.cancel()

    # --- Background Tasks ---

    @tasks.loop(minutes=1)
    async def backup_loop(self):
        """
        Background task that checks every minute if it's time for a scheduled backup.
        
        If the current time matches `backup_time` in `user_config.json`,
        it creates a named auto-backup.
        """
        await self.bot.wait_until_ready()
        
        try:
            # Load configs
            user_config = config.load_user_config()
            bot_config = config.load_bot_config()
            
            backup_time = user_config.get('backup_time', '03:00')
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # Check if times match
            if current_time == backup_time:
                # Check if already done today
                last_run = bot_config.get('last_auto_backup', '')
                today_str = now.strftime("%Y-%m-%d")
                
                if last_run != today_str:
                    logger.info(f"⏰ Starting scheduled backup (Time: {backup_time})")
                    
                    # Notify command channel if possible
                    cmd_channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
                    if cmd_channel:
                        await cmd_channel.send("⏳ Starting scheduled backup...")

                    success, filename, _ = await backup_manager.create_backup(server=self.bot.server)
                    
                    if success:
                        # Update last run
                        bot_config['last_auto_backup'] = today_str
                        config.save_bot_config(bot_config)
                        
                        if cmd_channel:
                            await cmd_channel.send(f"✅ Scheduled backup created: `{filename}`")
                    else:
                        logger.error(f"Scheduled backup failed: {filename}")
                        if cmd_channel:
                             await cmd_channel.send(f"❌ Scheduled backup failed: {filename}")

        except Exception as e:
            logger.error(f"Error in backup schedule loop: {e}")

    # --- Commands ---

    @app_commands.command(name="backup", description="Create a backup of the world")
    @app_commands.describe(name="Optional custom name for the backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup(self, interaction: discord.Interaction, name: str = None):
        """
        Creates a manual backup of the world.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            name (str, optional): A custom name for the backup file. Defaults to None.
        """
        await interaction.response.defer(ephemeral=True)
        
        await interaction.followup.send("⏳ Starting backup... This might take a moment.")
        
        success, filename, filepath = await backup_manager.create_backup(custom_name=name, server=self.bot.server)
        
        if success:
            view = BackupDownloadView(filepath)
            await interaction.followup.send(f"✅ Backup created successfully: `{filename}`", view=view, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Backup failed: {filename}", ephemeral=True)

    @app_commands.command(name="backup_list", description="List available backups")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_list(self, interaction: discord.Interaction):
        """
        Lists available world backups, grouped by type (Custom/Auto).

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
        """
        await interaction.response.defer(ephemeral=True)
        
        # Helper to get files
        def get_backups(directory):
            """
            Lists zip files in the specified directory.

            Args:
                directory (str): The path to the directory to list.

            Returns:
                list[str]: A list of filenames.
            """
            try:
                if not os.path.exists(directory):
                    return []
                return [f for f in os.listdir(directory) if f.endswith('.zip')]
            except Exception as e:
                logger.error(f"Failed to list backups in {directory}: {e}")
                return []

        auto_backups = await asyncio.to_thread(get_backups, backup_manager.auto_dir)
        custom_backups = await asyncio.to_thread(get_backups, backup_manager.custom_dir)
        
        # Sort by time
        auto_backups.sort(reverse=True)
        custom_backups.sort(reverse=True)
        
        msg = "📂 **Available Backups**\n\n**Custom**:\n"
        if custom_backups:
            msg += "\n".join([f"- `{f}`" for f in custom_backups[:5]])
            if len(custom_backups) > 5:
                msg += f"\n... and {len(custom_backups)-5} more"
        else:
            msg += "*None*"
            
        msg += "\n\n**Auto**:\n"
        if auto_backups:
            msg += "\n".join([f"- `{f}`" for f in auto_backups[:5]])
            if len(auto_backups) > 5:
                msg += f"\n... and {len(auto_backups)-5} more"
        else:
            msg += "*None*"
            
        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="backup_download", description="Download a specific backup directly")
    @app_commands.describe(filename="The backup file to download")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup_download(self, interaction: discord.Interaction, filename: str):
        """
        Sends a specific backup file to the user.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            filename (str): The name of the backup file to download.
        """
        await interaction.response.defer(ephemeral=True)

        filepath = None
        if os.path.exists(os.path.join(backup_manager.custom_dir, filename)):
            filepath = os.path.join(backup_manager.custom_dir, filename)
        elif os.path.exists(os.path.join(backup_manager.auto_dir, filename)):
            filepath = os.path.join(backup_manager.auto_dir, filename)

        if not filepath:
            await interaction.followup.send(f"❌ Backup `{filename}` not found.", ephemeral=True)
            return

        await interaction.followup.send("⏳ Preparing download...", ephemeral=True)
        try:
            await interaction.followup.send(file=discord.File(filepath), ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send backup file: {e}")
            await interaction.followup.send("❌ Failed to send the file.", ephemeral=True)

    @backup_download.autocomplete("filename")
    async def backup_download_autocomplete(self, interaction: discord.Interaction, current: str):
        """
        Provides autocomplete suggestions for backup filenames.

        Args:
            interaction (discord.Interaction): The interaction that triggered the autocomplete.
            current (str): The current input from the user.

        Returns:
            list[app_commands.Choice]: A list of autocomplete choices.
        """
        files = []
        for directory in (backup_manager.custom_dir, backup_manager.auto_dir):
            try:
                files.extend(f for f in os.listdir(directory) if f.endswith(".zip"))
            except (FileNotFoundError, OSError):
                pass
        files.sort(reverse=True)
        return [
            app_commands.Choice(name=f, value=f)
            for f in files
            if current.lower() in f.lower()
        ][:25]

# --- Views ---

class BackupDownloadView(discord.ui.View):
    """
    A view containing a button to download a backup file.

    Attributes:
        filepath (str): The path to the backup file.
        uploaded (bool): Flag to track if the file has been uploaded.
    """
    def __init__(self, filepath):
        """Initializes the view with the specified filepath."""
        super().__init__(timeout=120)
        self.filepath = filepath
        self.uploaded = False

    @discord.ui.button(label="Download", style=discord.ButtonStyle.primary, emoji="⬇️")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handles the download button click.

        Args:
            interaction (discord.Interaction): The interaction that triggered the click.
            button (discord.ui.Button): The button that was clicked.
        """
        await interaction.response.defer(ephemeral=True)

        if self.uploaded:
            await interaction.followup.send("Already sent!", ephemeral=True)
            return

        try:
            await interaction.followup.send(file=discord.File(self.filepath), ephemeral=True)
            self.uploaded = True
            button.disabled = True
            await interaction.edit_original_response(view=self)
        except Exception as e:
            logger.error(f"Failed to send backup file: {e}")
            await interaction.followup.send("❌ Failed to send the file.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BackupCog(bot))
