import discord
from discord.ext import commands
import asyncio
import re
from src.config import config
from src.logger import logger

# Log lines containing any of these strings are never shown to users
_LOG_NOISE = {
    "Thread RCON Listener started",
    "RCON running on",
    "RCON Listener #",
    "Stopping remote control listener",
    "UUID of player",
}

_DEATH_WORDS = [
    "was slain", "was shot", "drowned", "experienced kinetic energy",
    "blew up", "was killed", "hit the ground", "fell from",
    "went up in flames", "burned to death", "walked into fire",
    "tried to swim in lava", "died", "was squashed", "was pummeled",
    "was pricked", "starved to death", "suffocated", "was impaled",
    "was frozen", "withered away",
]


class PlayerTracker(commands.Cog):
    """Consumes the log stream to track player events and update bot presence.
    Does not send anything to the log channel — use /logs for on-demand output."""

    def __init__(self, bot):
        self.bot = bot
        self.log_task = None
        self.stop_event = asyncio.Event()

    async def cog_load(self):
        from src.log_dispatcher import log_dispatcher
        self.log_queue = log_dispatcher.subscribe()
        await log_dispatcher.start()
        self.log_task = asyncio.create_task(self._consume())

    async def cog_unload(self):
        self.stop_event.set()
        if self.log_task:
            self.log_task.cancel()
            try:
                await self.log_task
            except asyncio.CancelledError:
                pass

    async def _consume(self):
        await self.bot.wait_until_ready()
        logger.info("PlayerTracker: log consumer started")

        while not self.stop_event.is_set():
            try:
                line = await asyncio.wait_for(self.log_queue.get(), timeout=1.0)
                if not line:
                    continue

                match = re.search(r'\[(.*?)] \[(.*?)/(.*?)\]: (.*)', line)
                if not match:
                    continue

                _time, _thread, _level, msg = match.groups()

                if any(noise in msg for noise in _LOG_NOISE):
                    continue

                if "Starting minecraft server version" in msg:
                    await self.bot.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name="Server Starting..."),
                        status=discord.Status.idle
                    )

                elif "Done (" in msg and "! For help, type" in msg:
                    bot_config = config.load_bot_config()
                    count = len(bot_config.get('online_players', []))
                    await self.bot.change_presence(
                        activity=discord.Activity(type=discord.ActivityType.playing, name=f"Minecraft: {count} Players"),
                        status=discord.Status.online
                    )

                elif "joined the game" in msg:
                    m = re.match(r'^(\w+) joined the game', msg)
                    if m:
                        player = m.group(1)
                        bot_config = config.load_bot_config()
                        players = bot_config.get('online_players', [])
                        if player not in players:
                            players.append(player)
                            bot_config['online_players'] = players
                            config.save_bot_config(bot_config)
                        await self.bot.change_presence(
                            activity=discord.Activity(type=discord.ActivityType.playing, name=f"Minecraft: {len(players)} Players"),
                            status=discord.Status.online
                        )
                        await self.send_event_notification("join", player)

                elif "left the game" in msg:
                    m = re.match(r'^(\w+) left the game', msg)
                    if m:
                        player = m.group(1)
                        bot_config = config.load_bot_config()
                        players = bot_config.get('online_players', [])
                        if player in players:
                            players.remove(player)
                            bot_config['online_players'] = players
                            config.save_bot_config(bot_config)
                        await self.bot.change_presence(
                            activity=discord.Activity(type=discord.ActivityType.playing, name=f"Minecraft: {len(players)} Players"),
                            status=discord.Status.online
                        )
                        await self.send_event_notification("leave", player)

                elif any(word in msg for word in _DEATH_WORDS):
                    player = msg.split()[0] if msg else None
                    if player:
                        await self.send_event_notification("death", player, msg)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"PlayerTracker error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def send_event_notification(self, event_type: str, player_name: str, extra_msg: str = None):
        """Send player event notifications to the debug channel."""
        try:
            channel = self.bot.get_channel(config.DEBUG_CHANNEL_ID)
            if not channel:
                return

            if event_type == "join":
                message = f"🟢 **{player_name}** joined the game"
            elif event_type == "leave":
                message = f"🔴 **{player_name}** left the game"
            elif event_type == "death":
                message = f"💀 **{player_name}** died: {extra_msg}" if extra_msg else f"💀 **{player_name}** died"
            elif event_type == "command":
                message = f"🛡️ **{player_name}** {extra_msg}"
            else:
                return

            await channel.send(message)
        except Exception as e:
            logger.error(f"Failed to send event notification: {e}")


async def setup(bot):
    await bot.add_cog(PlayerTracker(bot))
