import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import os
from datetime import datetime
from src.utils import rcon_cmd, has_role
from src.config import config
from src.logger import logger

class AutomationCog(commands.Cog):
    """
    Handles automated background tasks such as:
    - Weekly MOTD updates via AI.
    - Scanning server logs for custom chat triggers (Regex/Keyword).
    """
    def __init__(self, bot):
        self.bot = bot
        self.log_task = None
        self.stop_scan = asyncio.Event()
        self.motd_loop.start()

    def cog_unload(self):
        if self.log_task:
            self.stop_scan.set()
            self.log_task.cancel()
        # Unsubscribe from log dispatcher to prevent memory leak
        if hasattr(self, 'log_queue'):
            from src.log_dispatcher import log_dispatcher
            log_dispatcher.unsubscribe(self.log_queue)

    async def cog_load(self):
        from src.log_dispatcher import log_dispatcher
        self.log_queue = log_dispatcher.subscribe()
        await log_dispatcher.start()
        self.log_task = asyncio.create_task(self.scan_logs_for_triggers())

    async def scan_logs_for_triggers(self):
        """
        Continuously scans the Docker container logs for Trigger phrases defined in `user_config.json`.
        
        Mechanism:
        - Subscribes to LogDispatcher queue.
        - Reads lines asynchronously.
        - Checks each line against configured triggers.
        - Executes RCON commands if a match is found.
        """
        await self.bot.wait_until_ready()
        logger.info("Starting Trigger Scanner...")
        
        while not self.stop_scan.is_set():
            try:
                logger.info("Trigger Scanner connected to log_dispatcher")
                
                while not self.stop_scan.is_set():
                    try:
                        line = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
                        
                        # Parse MC log format if needed, or just scan raw line
                        # Format: [HH:MM:SS] [Thread/LEVEL]: Message
                        clean_line = line
                        
                        if "[Bot]" in clean_line: continue # Skip bot's own messages (via RCON echo)

                        user_config = config.load_user_config()
                        triggers = user_config.get('triggers', {})
                        
                        lower_line = clean_line.lower()
                        
                        for trigger_phrase, response_cmd in triggers.items():
                            if trigger_phrase.lower() in lower_line:
                                logger.info(f"Trigger fired: '{trigger_phrase}' -> '{response_cmd}'")
                                await rcon_cmd(response_cmd)
                                
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                         logger.error(f"Error processing log line: {e}")
                         await asyncio.sleep(1)

                if not self.stop_scan.is_set():
                    logger.warning("Log stream ended, restarting scanner in 5s...")
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Trigger Scanner error: {e}")
                await asyncio.sleep(5)
                        

    @app_commands.command(name="trigger_add", description="Add a custom chat trigger")
    @has_role("trigger_admin")
    async def trigger_add(self, interaction: discord.Interaction, phrase: str, command: str):
        user_config = config.load_user_config()
        triggers = user_config.get('triggers', {})
        triggers[phrase] = command
        user_config['triggers'] = triggers
        
        config.save_user_config(user_config)
        
        await interaction.response.send_message(f"Added trigger: `{phrase}` -> `{command}`")

    @app_commands.command(name="trigger_list", description="List custom triggers")
    @has_role("trigger_list")
    async def trigger_list(self, interaction: discord.Interaction):
        user_config = config.load_user_config()
        triggers = user_config.get('triggers', {})
        
        if not triggers:
             await interaction.response.send_message("No triggers set.", ephemeral=True)
             return
             
        msg = "**Custom Triggers**\n"
        for k, v in triggers.items():
            msg += f"- `{k}` -> `{v}`\n"
            
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="trigger_remove", description="Remove a trigger")
    @has_role("trigger_admin")
    async def trigger_remove(self, interaction: discord.Interaction, phrase: str):
        user_config = config.load_user_config()
        triggers = user_config.get('triggers', {})
        
        if phrase in triggers:
            del triggers[phrase]
            config.save_user_config(user_config)
            await interaction.response.send_message(f"Removed trigger: `{phrase}`")
        else:
            await interaction.response.send_message("Trigger not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutomationCog(bot))
