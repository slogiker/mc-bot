import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.utils import rcon_cmd, has_role
from src.logger import logger


class ConsoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="logs", description="Post the last N lines from the server log to the log channel")
    @app_commands.describe(lines="Number of lines to show (default 30, max 100)")
    @has_role("logs")
    async def logs(self, interaction: discord.Interaction, lines: int = 30):
        await interaction.response.defer(ephemeral=True)

        lines = max(1, min(lines, 100))

        from src.log_dispatcher import log_dispatcher
        recent = log_dispatcher.get_recent_logs()
        slice_ = recent[-lines:]

        if not slice_:
            await interaction.followup.send("No log lines available yet.", ephemeral=True)
            return

        # Chunk into <=1900-char code blocks to stay under Discord's 2000-char limit
        chunks = []
        current = []
        current_len = 0
        for line in slice_:
            if current_len + len(line) + 1 > 1900:
                chunks.append(current)
                current = []
                current_len = 0
            current.append(line)
            current_len += len(line) + 1
        if current:
            chunks.append(current)

        log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            for chunk in chunks:
                await log_channel.send(f"```\n{chr(10).join(chunk)}\n```")
            await interaction.followup.send(f"Logs posted to {log_channel.mention}.", ephemeral=True)
        else:
            for chunk in chunks:
                await interaction.followup.send(f"```\n{chr(10).join(chunk)}\n```", ephemeral=True)

    @app_commands.command(name="cmd", description="Execute a command on the server (Owner only)")
    async def cmd(self, interaction: discord.Interaction, command: str):
        owner_id = config.OWNER_ID

        if not owner_id:
            app_info = await self.bot.application_info()
            if app_info.owner.id == interaction.user.id:
                bot_config = config.load_bot_config()
                bot_config['owner_id'] = interaction.user.id
                config.save_bot_config(bot_config)
            else:
                await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
                return
        elif str(interaction.user.id) != str(owner_id):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return

        await interaction.response.defer()

        logger.info(f"User {interaction.user.name} ({interaction.user.id}) executed RCON: {command}")

        # Notify debug channel
        player_tracker = self.bot.get_cog("PlayerTracker")
        if player_tracker:
            await player_tracker.send_event_notification("command", interaction.user.name, f"executed RCON command: `{command}`")

        response = await rcon_cmd(command)

        if len(response) > 1900:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for chunk in chunks:
                await interaction.followup.send(f"```{chunk}```")
        else:
            await interaction.followup.send(f"```{response}```")


async def setup(bot):
    await bot.add_cog(ConsoleCog(bot))
