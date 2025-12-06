import discord
from src.config import config

class ControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None) # Persistent view
        self.bot = bot

    @discord.ui.button(label="Start", style=discord.ButtonStyle.green, custom_id="mc_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if self.bot.server.is_running():
            await interaction.followup.send("✅ Server is already running.", ephemeral=True)
            return

        await interaction.followup.send("🚀 Starting server...", ephemeral=True)
        success = await self.bot.server.start()
        if not success:
            await interaction.followup.send("❌ Failed to start server.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, custom_id="mc_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.bot.server.is_running():
            await interaction.followup.send("✅ Server is already stopped.", ephemeral=True)
            return

        await interaction.followup.send("🛑 Stopping server...", ephemeral=True)
        success = await self.bot.server.stop()
        if not success:
            await interaction.followup.send("❌ Failed to stop server.", ephemeral=True)

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.blurple, custom_id="mc_restart")
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("🔄 Restarting server...", ephemeral=True)
        success = await self.bot.server.restart()
        if not success:
            await interaction.followup.send("❌ Failed to restart server.", ephemeral=True)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.gray, custom_id="mc_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Re-use status logic from info cog if possible, or just simple check
        status = "🟢 Online" if self.bot.server.is_running() else "🔴 Offline"
        await interaction.response.send_message(f"Server Status: **{status}**", ephemeral=True)
