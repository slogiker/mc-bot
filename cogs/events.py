import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from src.config import config
from src.logger import logger

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.event_loop.start()

    def cog_unload(self):
        self.event_loop.cancel()

    @tasks.loop(minutes=1)
    async def event_loop(self):
        """Checks for upcoming events and sends reminders."""
        bot_config = config.load_bot_config()
        events = bot_config.get('events', [])
        updated = False
        now = datetime.now()

        for event in events:
            try:
                event_time = datetime.fromisoformat(event['time'])
                
                # Reminders (24h and 1h)
                # We need to track if we already sent the reminder?
                # A simple way involves adding flags to the event dict.
                if 'reminded_24h' not in event: event['reminded_24h'] = False
                if 'reminded_1h' not in event: event['reminded_1h'] = False

                time_left = event_time - now
                
                # Check 24h (approximate match within last minute)
                if timedelta(hours=23, minutes=59) <= time_left <= timedelta(hours=24, minutes=1) and not event['reminded_24h']:
                    await self.send_reminder(event, "24 hours")
                    event['reminded_24h'] = True
                    updated = True
                
                # Check 1h
                if timedelta(minutes=59) <= time_left <= timedelta(hours=1, minutes=1) and not event['reminded_1h']:
                    await self.send_reminder(event, "1 hour")
                    event['reminded_1h'] = True
                    updated = True

            except Exception as e:
                logger.error(f"Error checking event {event.get('name')}: {e}")

        # Cleanup old events (keep for 24h after for history maybe? or delete immediately)
        # Let's delete events that are > 24h past
        active_events = []
        for event in events:
             try:
                 event_time = datetime.fromisoformat(event['time'])
                 if now - event_time < timedelta(hours=24):
                     active_events.append(event)
                 else:
                     updated = True # One removed
             except:
                 pass
        
        if updated:
            bot_config['events'] = active_events
            config.save_bot_config(bot_config)

    async def send_reminder(self, event, time_left_str):
        channel_id = config.LOG_CHANNEL_ID # Dynamically assigned during setup
        channel = self.bot.get_channel(channel_id)
        if not channel: return
        
        mentions = event.get('mentions', '')
        embed = discord.Embed(title=f"📅 Event Reminder: {event['name']}", color=discord.Color.blue())
        embed.description = f"Starting in **{time_left_str}**!\n\n{event.get('description', '')}"
        
        # Format timestamp
        ts = int(datetime.fromisoformat(event['time']).timestamp())
        embed.add_field(name="Time", value=f"<t:{ts}:F> (<t:{ts}:R>)")
        
        await channel.send(content=mentions, embed=embed)

    @app_commands.command(name="event_create", description="Schedule a new server event")
    @app_commands.describe(time="Format: YYYY-MM-DD HH:MM (24h)")
    # TODO: Add permission check (e.g. @has_role('event_manage'))
    async def create_event(self, interaction: discord.Interaction, name: str, time: str, description: str = "", mentions: str = ""):
        try:
            event_dt = datetime.strptime(time, "%Y-%m-%d %H:%M")
            if event_dt < datetime.now():
                await interaction.response.send_message("❌ Time must be in the future.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Invalid time format. Use `YYYY-MM-DD HH:MM` (e.g., 2026-05-20 18:00)", ephemeral=True)
            return

        bot_config = config.load_bot_config()
        events = bot_config.get('events', [])
        
        new_event = {
            "name": name,
            "time": event_dt.isoformat(),
            "description": description,
            "mentions": mentions,
            "creator": interaction.user.id,
            "reminded_24h": False,
            "reminded_1h": False
        }
        
        events.append(new_event)
        bot_config['events'] = events
        config.save_bot_config(bot_config)
        
        embed = discord.Embed(title="✅ Event Created", color=discord.Color.green())
        embed.add_field(name="Name", value=name)
        embed.add_field(name="Time", value=f"<t:{int(event_dt.timestamp())}:F>")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="event_list", description="List upcoming events")
    async def list_events(self, interaction: discord.Interaction):
        bot_config = config.load_bot_config()
        events = bot_config.get('events', [])
        
        if not events:
            await interaction.response.send_message("📅 No upcoming events.", ephemeral=True)
            return
            
        # Sort by time
        events.sort(key=lambda x: x['time'])
        
        embed = discord.Embed(title="📅 Upcoming Events", color=discord.Color.blue())
        for i, event in enumerate(events):
            ts = int(datetime.fromisoformat(event['time']).timestamp())
            embed.add_field(
                name=f"{i+1}. {event['name']}",
                value=f"<t:{ts}:R> | {event.get('description', 'No description')}",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="event_delete", description="Delete an event")
    # TODO: Add permission check
    async def delete_event(self, interaction: discord.Interaction, index: int):
        bot_config = config.load_bot_config()
        events = bot_config.get('events', [])
        
        if index < 1 or index > len(events):
            await interaction.response.send_message("❌ Invalid event index.", ephemeral=True)
            return
            
        deleted = events.pop(index - 1)
        bot_config['events'] = events
        config.save_bot_config(bot_config)
        
        await interaction.response.send_message(f"🗑️ Deleted event: **{deleted['name']}**", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
