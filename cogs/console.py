import discord
from discord import app_commands
from discord.ext import commands
import re
from src.config import config
from src.utils import rcon_cmd, has_role
from src.logger import logger

class LogsView(discord.ui.View):
    def __init__(self, bot, initial_filter="default"):
        super().__init__(timeout=600)
        self.bot = bot
        self.current_filter = initial_filter
        self._update_buttons()

    def _update_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label:
                # Disable the button for the current filter
                label_map = {
                    "default": "Default (Filtered)",
                    "chat": "Chat Only",
                    "errors": "Errors/Warnings",
                    "joins": "Joins/Leaves",
                    "raw": "Raw/All"
                }
                child.disabled = (label_map.get(self.current_filter) == child.label)

    def _filter_logs(self, lines):
        if self.current_filter == "raw":
            return lines
        
        filtered = []
        for line in lines:
            # Strip RCON noise by default for all other filters
            if "RCON Client" in line or "issued server command: /list" in line:
                continue
                
            if self.current_filter == "chat":
                if re.search(r"<.+> .*", line):
                    filtered.append(line)
            elif self.current_filter == "errors":
                if any(x in line.upper() for x in ["ERROR", "EXCEPTION", "WARN", "WARNING"]):
                    filtered.append(line)
            elif self.current_filter == "joins":
                if any(x in line for x in ["joined the game", "left the game", "logged in with entity id"]):
                    filtered.append(line)
            elif self.current_filter == "default":
                # Joins, Leaves, Deaths, Chat, Errors, Warnings
                if any(x in line for x in ["joined the game", "left the game", "logged in with entity id", "died", "was slain by", "was blown up by"]) or \
                   re.search(r"<.+> .*", line) or \
                   any(x in line.upper() for x in ["ERROR", "EXCEPTION", "WARN", "WARNING"]):
                    filtered.append(line)
        return filtered

    def _format_logs(self, lines):
        if not lines:
            return "```log\nNo logs found for this filter.\n```"
            
        WRAPPER_OVERHEAD = 11 # ```log\n\n```
        MAX_LENGTH = 2000 - WRAPPER_OVERHEAD
        
        formatted_lines = []
        current_length = 0
        
        # Newest logs are at the end, so we iterate backwards
        for line in reversed(lines):
            line_len = len(line) + 1 # +1 for newline
            if current_length + line_len > MAX_LENGTH:
                formatted_lines.insert(0, "...")
                break
            formatted_lines.insert(0, line)
            current_length += line_len
            
        return f"```log\n" + "\n".join(formatted_lines) + "\n```"

    async def _update_message(self, interaction: discord.Interaction):
        from src.log_dispatcher import log_dispatcher
        all_logs = log_dispatcher.get_recent_logs()
        filtered = self._filter_logs(all_logs)
        content = self._format_logs(filtered)
        
        self._update_buttons()
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Default (Filtered)", style=discord.ButtonStyle.success)
    async def default_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_filter = "default"
        await self._update_message(interaction)

    @discord.ui.button(label="Chat Only", style=discord.ButtonStyle.primary)
    async def chat_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_filter = "chat"
        await self._update_message(interaction)

    @discord.ui.button(label="Errors/Warnings", style=discord.ButtonStyle.danger)
    async def error_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_filter = "errors"
        await self._update_message(interaction)

    @discord.ui.button(label="Joins/Leaves", style=discord.ButtonStyle.secondary)
    async def join_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_filter = "joins"
        await self._update_message(interaction)

    @discord.ui.button(label="Raw/All", style=discord.ButtonStyle.gray)
    async def raw_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_filter = "raw"
        await self._update_message(interaction)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.green, row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_message(interaction)

class ConsoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="logs", description="View Minecraft server logs with filtering")
    @has_role("logs")
    async def logs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        from src.log_dispatcher import log_dispatcher
        recent = log_dispatcher.get_recent_logs()
        
        view = LogsView(self.bot)
        filtered = view._filter_logs(recent)
        content = view._format_logs(filtered)
        
        await interaction.followup.send(content=content, view=view, ephemeral=True)

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

        success, response = await rcon_cmd(command)
        
        if isinstance(response, tuple):
            response = response[0]

        if len(response) > 1900:
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for chunk in chunks:
                await interaction.followup.send(f"```{chunk}```")
        else:
            await interaction.followup.send(f"```{response}```")


async def setup(bot):
    await bot.add_cog(ConsoleCog(bot))
