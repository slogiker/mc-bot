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
        logger.info("Starting docker log tailing task...")

        while not self.stop_event.is_set():
            try:
                channel_id = config.LOG_CHANNEL_ID
                if not channel_id:
                    await asyncio.sleep(10)
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    await asyncio.sleep(10)
                    continue

                # Start docker logs process
                process = await asyncio.create_subprocess_exec(
                    'docker', 'logs', '-f', '--tail', '0', 'mc-bot',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )

                logger.info("Connected to docker logs stream")
                
                # Batch buffer for messages
                batch = []
                last_send = asyncio.get_event_loop().time()
                batch_interval = 2.0  # Send every 2 seconds or when batch is full
                max_batch_size = 10  # Max messages per batch

                while not self.stop_event.is_set():
                    try:
                        line_bytes = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=1.0
                        )
                        
                        if not line_bytes:
                            break  # EOF
                        
                        line = line_bytes.decode('utf-8', errors='ignore').strip()
                        if not line:
                            continue

                        # Parse MC log format: [HH:MM:SS] [Thread/LEVEL]: Message
                        match = re.search(r'\[(.*?)] \[(.*?)/(.*?)\]: (.*)', line)
                        if match:
                            time_str, thread, level, msg = match.groups()
                            
                            # Skip blacklisted messages
                            user_config = config.load_user_config()
                            if any(b in msg for b in user_config.get('log_blacklist', [])):
                                continue

                            # Format: [LEVEL] message
                            formatted = f"[{level}] {msg}"
                            batch.append(formatted)
                            
                            # --- Player tracking for presence ---
                            if "joined the game" in msg:
                                player_name = msg.split(" joined the game")[0].strip()
                                bot_config = config.load_bot_config()
                                current_players = bot_config.get('online_players', [])
                                if player_name not in current_players:
                                    current_players.append(player_name)
                                    bot_config['online_players'] = current_players
                                    config.save_bot_config(bot_config)
                                await self.update_presence(len(current_players))
                                # Send notification to debug channel
                                await self.send_event_notification("join", player_name)
                                
                            elif "left the game" in msg:
                                player_name = msg.split(" left the game")[0].strip()
                                bot_config = config.load_bot_config()
                                current_players = bot_config.get('online_players', [])
                                if player_name in current_players:
                                    current_players.remove(player_name)
                                    bot_config['online_players'] = current_players
                                    config.save_bot_config(bot_config)
                                await self.update_presence(len(current_players))
                                # Send notification to debug channel
                                await self.send_event_notification("leave", player_name)
                            
                            # Death detection (various death messages)
                            elif any(death_word in msg for death_word in ["was slain", "was shot", "drowned", "experienced kinetic energy", "blew up", "was killed", "hit the ground", "fell from", "went up in flames", "burned to death", "walked into fire", "tried to swim in lava", "died", "was squashed", "was pummeled", "was pricked", "starved to death", "suffocated", "was impaled", "was frozen", "withered away"]):
                                # Extract player name (usually first word before death message)
                                player_name = msg.split()[0] if msg else None
                                if player_name:
                                    await self.send_event_notification("death", player_name, msg)

                        # Send batch if full or time elapsed
                        current_time = asyncio.get_event_loop().time()
                        if len(batch) >= max_batch_size or (batch and current_time - last_send >= batch_interval):
                            # Send as code block
                            message = "```ansi\n" + "\n".join(batch) + "\n```"
                            try:
                                await channel.send(message[:2000])  # Discord limit
                            except discord.HTTPException as e:
                                logger.warning(f"Failed to send log batch: {e}")
                            
                            batch = []
                            last_send = current_time

                    except asyncio.TimeoutError:
                        # No data for 1 second, check if we have pending batch
                        if batch:
                            current_time = asyncio.get_event_loop().time()
                            if current_time - last_send >= batch_interval:
                                message = "```ansi\n" + "\n".join(batch) + "\n```"
                                try:
                                    await channel.send(message[:2000])
                                except discord.HTTPException:
                                    pass
                                batch = []
                                last_send = current_time
                        continue

                # Process terminated, restart after delay
                await process.wait()
                logger.warning("Docker logs process ended, restarting in 5 seconds...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in log tailing: {e}", exc_info=True)
                await asyncio.sleep(5)
            
            await asyncio.sleep(1)

    async def send_event_notification(self, event_type: str, player_name: str, extra_msg: str = None):
        """Send player event notifications to debug channel with mentions"""
        try:
            debug_channel_id = config.DEBUG_CHANNEL_ID
            if not debug_channel_id:
                return
            
            debug_channel = self.bot.get_channel(debug_channel_id)
            if not debug_channel:
                return
            
            # Format message based on event type
            if event_type == "join":
                message = f"🟢 **{player_name}** joined the game"
            elif event_type == "leave":
                message = f"🔴 **{player_name}** left the game"
            elif event_type == "death":
                message = f"💀 **{player_name}** died: {extra_msg}" if extra_msg else f"💀 **{player_name}** died"
            else:
                return
            
            await debug_channel.send(message)
            
        except Exception as e:
            logger.error(f"Failed to send event notification: {e}")

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
