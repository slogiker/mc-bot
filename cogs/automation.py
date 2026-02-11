import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import os
import random
import aiofiles
from datetime import datetime
from src.utils import rcon_cmd
from utils.config import load_user_config, load_bot_config, save_user_config
from src.logger import logger
from src.config import config as main_config

class AutomationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.motd_loop.start()
        self.log_scan_task = None
        self.stop_scan = asyncio.Event()

    def cog_unload(self):
        self.motd_loop.cancel()
        if self.log_scan_task:
            self.stop_scan.set()
            self.log_scan_task.cancel()

    async def cog_load(self):
        self.log_scan_task = asyncio.create_task(self.scan_logs_for_triggers())

    @tasks.loop(hours=168) # Weekly
    async def motd_loop(self):
        """
        Updates the server MOTD once a week using AI generation if enabled.
        Requires an AI provider (xAI) and a server plugin supporting /setmotd (e.g., Essentials).
        """
        await self.bot.wait_until_ready()
        
        try:
             # Check if AI is available
             from cogs.ai import HAS_XAI, AICog
             ai_cog = self.bot.get_cog('AICog')
             
             if ai_cog and ai_cog.client:
                 logger.info("Generating AI MOTD...")
                 try:
                     completion = ai_cog.client.chat.completions.create(
                        model="grok-beta",
                        messages=[
                            {"role": "system", "content": "Generate a short, funny, Minecraft JSON MOTD description. Return ONLY the raw text/json valid for server.properties 'motd=' line."},
                            {"role": "user", "content": "Generate a new MOTD"}
                        ]
                     )
                     new_motd = completion.choices[0].message.content.replace("\n", " ")
                     
                     # Try to set via RCON (requires plugin like Essentials/CMI)
                     resp = await rcon_cmd(f'setmotd {new_motd}')
                     
                     if "Unknown command" in resp:
                         logger.warning("Could not set MOTD via RCON (command 'setmotd' not found). Server plugin required.")
                     else:
                         logger.info(f"MOTD updated: {new_motd}")
                         
                 except Exception as e:
                     logger.error(f"Failed to generate/set AI MOTD: {e}")
             
        except Exception as e:
            logger.error(f"Error in MOTD loop: {e}")

    @app_commands.command(name="motd", description="Set the server MOTD (requires plugin or restart)")
    async def set_motd(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer()
        resp = await rcon_cmd(f'setmotd {text}')
        await interaction.followup.send(f"🖥️ RCON Response: `{resp}`")

    async def scan_logs_for_triggers(self):
        """Scans logs effectively for context-aware triggers."""
        await self.bot.wait_until_ready()
        logger.info("Starting Trigger Scanner...")
        
        while not self.stop_scan.is_set():
            try:
                server_path = main_config.SERVER_DIR
                log_path = os.path.join(server_path, 'logs', 'latest.log')
                
                if not os.path.exists(log_path):
                    await asyncio.sleep(5)
                    continue

                # We need a position tracker distinct from console cog
                # Or we risk race conditions/file lock contention if we are not careful?
                # Actually, reading is fine.
                # Simplest way: Seek to end initially, then read new lines.
                
                async with aiofiles.open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    await f.seek(0, os.SEEK_END)
                    
                    while not self.stop_scan.is_set():
                        line = await f.readline()
                        if not line:
                            await asyncio.sleep(0.5)
                            continue
                            
                        # Process Trigger
                        user_config = load_user_config()
                        triggers = user_config.get('triggers', {})
                        # Triggers format: { "phrase": "command" }
                        # User wants context aware: "if phrase in line"
                        
                        lower_line = line.lower()
                        
                        for trigger_phrase, response_cmd in triggers.items():
                            if trigger_phrase.lower() in lower_line:
                                # Found a match!
                                # Execute response
                                # Safety: prevent infinite loops (bot says trigger -> triggers bot)
                                if "[Bot]" in line: continue
                                
                                # Random chance? User didn't specify, but nice to have.
                                # "it needs to be taken from any context there is happening"
                                
                                logger.info(f"Trigger fired: '{trigger_phrase}' -> '{response_cmd}'")
                                
                                # Process placeholders if any
                                # e.g. {player} if we can extract it.
                                # Simple extraction: if line has <Player>, use it.
                                
                                await rcon_cmd(response_cmd)
                                
                        # Trigger system for roasts/AI (if enabled and logic fits here)
                        # e.g. "killed by" -> roast
                        
            except Exception as e:
                logger.error(f"Trigger Scanner error: {e}")
                await asyncio.sleep(5)

    @app_commands.command(name="trigger_add", description="Add a custom chat trigger")
    async def trigger_add(self, interaction: discord.Interaction, phrase: str, command: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        user_config = load_user_config()
        triggers = user_config.get('triggers', {})
        triggers[phrase] = command
        user_config['triggers'] = triggers
        
        save_user_config(user_config)
        
        await interaction.response.send_message(f"✅ Added trigger: `{phrase}` -> `{command}`")

    @app_commands.command(name="trigger_list", description="List custom triggers")
    async def trigger_list(self, interaction: discord.Interaction):
        user_config = load_user_config()
        triggers = user_config.get('triggers', {})
        
        if not triggers:
             await interaction.response.send_message("No triggers set.", ephemeral=True)
             return
             
        msg = "🔀 **Custom Triggers**\n"
        for k, v in triggers.items():
            msg += f"- `{k}` → `{v}`\n"
            
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="trigger_remove", description="Remove a trigger")
    async def trigger_remove(self, interaction: discord.Interaction, phrase: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        user_config = load_user_config()
        triggers = user_config.get('triggers', {})
        
        if phrase in triggers:
            del triggers[phrase]
            save_user_config(user_config)
            await interaction.response.send_message(f"🗑️ Removed trigger: `{phrase}`")
        else:
            await interaction.response.send_message("❌ Trigger not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutomationCog(bot))
