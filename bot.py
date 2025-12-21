import discord
from discord import app_commands
from discord.ext import commands
import argparse
import asyncio
import sys
import os
from src.config import config
from src.logger import logger
from src.server_tmux import TmuxServerManager
from src.server_mock import MockServerManager

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Minecraft Discord Bot")
parser.add_argument("--test", action="store_true", help="Run in Test Mode (Mock Server)")
args = parser.parse_args()

# --- Configuration Setup ---
config.set_test_mode(args.test)
if config.TEST_MODE:
    logger.info("⚠️ STARTING IN TEST MODE (MOCK SERVER) ⚠️")

# --- Bot Setup ---
class MinecraftBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='/', intents=intents)
        
        # Initialize Server Manager
        if config.TEST_MODE:
            self.server = MockServerManager(self)
        else:
            self.server = TmuxServerManager()

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"⏳ Command is on cooldown. Try again in {error.retry_after:.2f}s.", ephemeral=True)
        elif isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ You cannot use this command here.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)
            logger.error(f"Command error: {error}")

    async def setup_hook(self):
        self.tree.on_error = self.on_tree_error
        
        logger.info("=== Bot Startup: Loading Extensions ===")
        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != '__init__.py':
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("=== Bot Connected ===")
        
        # Determine which Guild to use
        # If config has a specific GUILD_ID, try to find it. Otherwise use the first one.
        guild = None
        if config.GUILD_ID:
             # GUILD_ID might be a string in config
             guild = self.get_guild(int(config.GUILD_ID))
        
        if not guild and self.guilds:
             guild = self.guilds[0]
             
        if not guild:
            logger.error("Bot is not in any guilds! Cannot perform setup.")
            return

        logger.info(f"Using Guild: {guild.name} ({guild.id})")

        # Run Dynamic Setup
        from src.setup_helper import SetupHelper
        setup_helper = SetupHelper(self)
        try:
             updates = await setup_helper.ensure_setup(guild)
             config.update_dynamic_config(updates)
             logger.info(f"Dynamic Config Updated: {updates}")
        except Exception as e:
             logger.error(f"Dynamic Setup Failed: {e}")
        
        # Sync commands to this guild
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced commands to guild")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        # Update presence based on initial state
        if self.server.is_running():
             await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Online"), status=discord.Status.online)
        else:
             await self.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Offline"), status=discord.Status.dnd)

async def main():
    bot = MinecraftBot()
    token = config.TEST_BOT_TOKEN if config.TEST_MODE else config.TOKEN
    
    if not token:
        logger.error("No token found! Check config.")
        return

    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
