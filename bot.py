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
parser.add_argument("--dry-run", action="store_true", help="Run in Dry-Run Mode (Preview changes without applying)")
args = parser.parse_args()

# --- Configuration Setup ---
config.set_test_mode(args.test)
config.set_dry_run_mode(args.dry_run)

if config.DRY_RUN_MODE:
    logger.info("🌵 STARTING IN DRY-RUN MODE (PREVIEW ONLY) 🌵")
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
        
        self.synced = False  # Prevent duplicate syncs

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
        """Called during bot startup - load extensions but DON'T sync yet"""
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
        
        logger.info("=== All extensions loaded ===")

    async def on_ready(self):
        """Called when bot is fully connected and ready"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("=== Bot Connected to Discord ===")
        
        # Only sync once
        if self.synced:
            logger.info("Commands already synced, skipping...")
            return
        
        # Determine which Guild to use
        guild = None
        if config.GUILD_ID:
            try:
                guild = self.get_guild(int(config.GUILD_ID))
            except (ValueError, TypeError):
                logger.warning(f"Invalid GUILD_ID: {config.GUILD_ID}")
        
        if not guild and self.guilds:
            guild = self.guilds[0]
            logger.info(f"No GUILD_ID configured, using first guild: {guild.name}")
             
        if not guild:
            logger.error("Bot is not in any guilds! Cannot perform setup.")
            logger.error("Please invite the bot to your Discord server.")
            return

        logger.info(f"Using Guild: {guild.name} ({guild.id})")

        # Run Dynamic Setup
        logger.info("Running dynamic setup...")
        from src.setup_helper import SetupHelper
        setup_helper = SetupHelper(self)
        try:
            updates = await setup_helper.ensure_setup(guild)
            config.update_dynamic_config(updates)
            logger.info(f"Dynamic Config Updated: {updates}")
        except Exception as e:
            logger.error(f"Dynamic Setup Failed: {e}", exc_info=True)
        
        # Sync commands to this guild
        logger.info("Syncing slash commands to guild...")
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"✅ Synced {len(synced)} commands to {guild.name}")
            self.synced = True
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}", exc_info=True)
            return

        # Update presence based on initial state
        logger.info("Setting bot presence...")
        try:
            if self.server.is_running():
                await self.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Online"),
                    status=discord.Status.online
                )
            else:
                await self.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.playing, name="Minecraft Server: Offline"),
                    status=discord.Status.dnd
                )
        except Exception as e:
            logger.error(f"Failed to set presence: {e}")
        
        logger.info("=== Bot is now fully ready! ===")

async def main():
    bot = MinecraftBot()
    token = config.TEST_BOT_TOKEN if config.TEST_MODE else config.TOKEN
    
    if not token:
        logger.error("No token found! Check .env file for BOT_TOKEN")
        return

    logger.info("Starting bot client...")
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)