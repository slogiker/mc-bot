import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
import os
import aiofiles
from datetime import datetime
from datetime import datetime
from src.config import config
from src.utils import rcon_cmd
from src.logger import logger

class ConsoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_task = None
        self.stop_event = asyncio.Event()

    async def cog_load(self):
        self.log_task = asyncio.create_task(self.tail_logs())

    async def cog_unload(self):
        if self.log_task:
            self.stop_event.set()
            self.log_task.cancel()
            try:
                await self.log_task
            except asyncio.CancelledError:
                pass

    async def tail_logs(self):
        await self.bot.wait_until_ready()
        logger.info("Starting log tailing task...")

        while not self.stop_event.is_set():
            try:
                bot_config = config.load_bot_config()
                # Ensure server path is correct. Using config.SERVER_DIR as primary source.
                server_path = config.SERVER_DIR
                log_path = os.path.join(server_path, 'logs', 'latest.log')
                
                channel_id = config.LOG_CHANNEL_ID
                if not channel_id:
                    # Try to find existing channel or wait for setup
                    await asyncio.sleep(10)
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                     # Channel might have been deleted
                     await asyncio.sleep(10)
                     continue

                if not os.path.exists(log_path):
                    await asyncio.sleep(5)
                    continue

                pos = bot_config.get('log_pos', 0)
                
                # Check for file rotation (size turned smaller)
                file_size = os.path.getsize(log_path)
                if file_size < pos:
                    pos = 0

                async with aiofiles.open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    await f.seek(pos)
                    lines = await f.readlines()
                    if not lines:
                         # No new lines, update pos just in case
                         pos = await f.tell()
                    else:
                        pos = await f.tell()
                        
                        # Process lines
                        chunk = ""
                        for line in lines:
                             # Basic filtering
                             if not line.strip(): continue
                             
                             # Regex parsing
                             # Default MC log format: [HH:MM:SS] [Thread/LEVEL]: Message
                             match = re.search(r'\[(.*?)] \[(.*?)/(.*?)\]: (.*)', line)
                             if match:
                                 time_str, thread, level, msg = match.groups()
                                 
                                 # Skip blacklisted
                                 user_config = config.load_user_config()
                                 if any(b in msg for b in user_config.get('log_blacklist', [])):
                                     continue

                                 # Color coding
                                 color = discord.Color.default()
                                 if "INFO" in level: color = discord.Color.green()
                                 elif "WARN" in level: color = discord.Color.gold()
                                 elif "ERROR" in level or "FATAL" in level: color = discord.Color.red()
                                 
                                 # We can either send embeds or code blocks.
                                 # Code blocks are more compact for a console feel. 
                                 # But user requested "Live Console Channel... Real-time colored log tail"
                                 # Discord code blocks with ansi colors are good, but embeds are also fine.
                                 
                                 embed = discord.Embed(description=msg, color=color, timestamp=datetime.now())
                                 embed.set_footer(text=f"{level} | {thread}")
                                 
                                 # Grouping or sending individually? 
                                 # Individual embeds might hit rate limits fast if there's log spam.
                                 # For V1, let's try individual but handle rate limits by sleeping if needed?
                                 # Better: Batching. But for now following prompts snippet roughly.
                                 
                                 try:
                                     await channel.send(embed=embed)
                                 except discord.HTTPException as e:
                                     logger.warning(f"Failed to send log to console channel: {e}")
                                     await asyncio.sleep(1) # Backoff
                                 
                                 # --- Presence Update Logic ---
                                 if "joined the game" in msg:
                                     player_name = msg.split(" joined the game")[0]
                                     current_players = bot_config.get('online_players', [])
                                     if player_name not in current_players:
                                         current_players.append(player_name)
                                         bot_config['online_players'] = current_players
                                         config.save_bot_config(bot_config)
                                     await self.update_presence(len(current_players))
                                     
                                 elif "left the game" in msg:
                                     player_name = msg.split(" left the game")[0]
                                     current_players = bot_config.get('online_players', [])
                                     if player_name in current_players:
                                         current_players.remove(player_name)
                                         bot_config['online_players'] = current_players
                                         config.save_bot_config(bot_config)
                                     await self.update_presence(len(current_players))

                             else:
                                 # Unformatted line (tracebacks etc)
                                 # Send as plain text or embed
                                 if line.strip():
                                     await channel.send(f"```{line.strip()}```")

                # Save position
                if pos != bot_config.get('log_pos'):
                    bot_config['log_pos'] = pos
                    config.save_bot_config(bot_config)

            except Exception as e:
                logger.error(f"Error in log tailing: {e}")
                await asyncio.sleep(5)
            
            await asyncio.sleep(1)

    async def update_presence(self, player_count):
        activity = discord.Activity(
            type=discord.ActivityType.playing, 
            name=f"Minecraft Server: Online",
            state=f"Players: {player_count}" # 'state' shows up as description in some contexts
        )
        # Rich presence limits strictly what can be shown. 
        # ActivityType.playing name is what shows "Playing X".
        # We can put "Minecraft | 5 Players" in name.
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=f"Minecraft: {player_count} Players"))


    @app_commands.command(name="cmd", description="Execute a command on the server (Owner only)")
    async def cmd(self, interaction: discord.Interaction, command: str):
        # Owner check
        # Use config.OWNER_ID directly
        owner_id = config.OWNER_ID
        
        # Fallback to checking app info if owner_id not set in config
        if not owner_id:
            app_info = await self.bot.application_info()
            if app_info.owner.id == interaction.user.id:
                # Save it for later
                bot_config = config.load_bot_config()
                bot_config['owner_id'] = interaction.user.id
                config.save_bot_config(bot_config)
            else:
                 await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
                 return
        elif str(interaction.user.id) != str(owner_id):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return

        # Execute
        await interaction.response.defer()
        response = await rcon_cmd(command)
        
        # Reply in thread logic (optional, but user requested 'replies appear in thread or as reply')
        # Simple reply is fine for now.
        
        if len(response) > 1900:
            # Chunking
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(f"```{chunk}```")
                else:
                    await interaction.followup.send(f"```{chunk}```")
        else:
             await interaction.followup.send(f"```{response}```")

async def setup(bot):
    await bot.add_cog(ConsoleCog(bot))
