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
    Manages world backups.
    Features:
    - Manual backups via /backup.
    - Scheduled backups (daily at configured time).
    - Ephemeral download links via `pyonesend`.
    """
    def __init__(self, bot):
        self.bot = bot
        self.backup_loop.start()

    def cog_unload(self):
        self.backup_loop.cancel()

    @tasks.loop(minutes=1)
    async def backup_loop(self):
        """
        Background task that checks every minute if the current time matches 
        the configured `backup_time` in `user_config.json`.
        If triggered, creates a named auto-backup (e.g., auto_2026-05-20).
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

                    success, filename, _ = await backup_manager.create_backup(custom_name=f"auto_{today_str}")
                    
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

    @app_commands.command(name="backup", description="Create a backup of the world")
    @app_commands.describe(name="Optional custom name for the backup")
    async def backup(self, interaction: discord.Interaction, name: str = None):
        await interaction.response.defer(ephemeral=True)
        
        await interaction.followup.send("⏳ Starting backup... This might take a moment.")
        
        success, filename, filepath = await backup_manager.create_backup(custom_name=name)
        
        if success:
            view = BackupDownloadView(filepath)
            await interaction.followup.send(f"✅ Backup created successfully: `{filename}`", view=view, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Backup failed: {filename}", ephemeral=True)

    @app_commands.command(name="backup_list", description="List available backups")
    async def backup_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Helper to get files
        def get_backups(directory):
            try:
                if not os.path.exists(directory): return []
                return [f for f in os.listdir(directory) if f.endswith('.zip')]
            except: return []

        auto_backups = await asyncio.to_thread(get_backups, backup_manager.auto_dir)
        custom_backups = await asyncio.to_thread(get_backups, backup_manager.custom_dir)
        
        # Sort by time
        auto_backups.sort(reverse=True)
        custom_backups.sort(reverse=True)
        
        msg = "📂 **Available Backups**\n\n**Custom**:\n"
        if custom_backups:
            msg += "\n".join([f"- `{f}`" for f in custom_backups[:5]])
            if len(custom_backups) > 5: msg += f"\n... and {len(custom_backups)-5} more"
        else:
            msg += "*None*"
            
        msg += "\n\n**Auto**:\n"
        if auto_backups:
            msg += "\n".join([f"- `{f}`" for f in auto_backups[:5]])
            if len(auto_backups) > 5: msg += f"\n... and {len(auto_backups)-5} more"
        else:
            msg += "*None*"
            
        await interaction.followup.send(msg, ephemeral=True)

    @app_commands.command(name="backup_download", description="Get a download link for a specific backup")
    @app_commands.describe(filename="The exact filename of the backup")
    async def backup_download(self, interaction: discord.Interaction, filename: str):
        await interaction.response.defer(ephemeral=True)
        
        # Search for file
        filepath = None
        if os.path.exists(os.path.join(backup_manager.custom_dir, filename)):
            filepath = os.path.join(backup_manager.custom_dir, filename)
        elif os.path.exists(os.path.join(backup_manager.auto_dir, filename)):
            filepath = os.path.join(backup_manager.auto_dir, filename)
            
        if not filepath:
            await interaction.followup.send(f"❌ Backup `{filename}` not found.", ephemeral=True)
            return

        await interaction.followup.send("⏳ Uploading backup...", ephemeral=True)
        link = await backup_manager.upload_backup(filepath)
        
        if link:
            await interaction.followup.send(f"✅ Download ready: {link}\n*(Link expires in 1 hour)*", ephemeral=True)
        else:
            await interaction.followup.send("❌ Upload failed.", ephemeral=True)

class BackupDownloadView(discord.ui.View):
    def __init__(self, filepath):
        super().__init__(timeout=120)
        self.filepath = filepath
        self.uploaded = False

    @discord.ui.button(label="Upload & Download", style=discord.ButtonStyle.primary, emoji="☁️")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if self.uploaded:
             await interaction.followup.send("Already uploaded!", ephemeral=True)
             return
             
        await interaction.followup.send("⏳ Uploading...", ephemeral=True)
        link = await backup_manager.upload_backup(self.filepath)
        
        if link:
            await interaction.followup.send(f"✅ Download Link: {link}\n*(Expires naturally via provider)*", ephemeral=True)
            self.uploaded = True
            button.disabled = True
            await interaction.edit_original_response(view=self)
        else:
            await interaction.followup.send("❌ Upload failed.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BackupCog(bot))
