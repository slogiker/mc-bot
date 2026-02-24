import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from src.config import config
from src.logger import logger
from src.utils import has_role, rcon_cmd
import asyncio

class ControlPanelView(ui.View):
    def __init__(self, bot):
        # Timeout None so the buttons never expire
        super().__init__(timeout=None)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # We can implement basic role checks here or rely on the actual command logic
        # For safety, let's verify if they have any management role.
        # But to be exact, we should check specific roles per button.
        return True

    @ui.button(label="Start", style=discord.ButtonStyle.success, emoji="▶️", custom_id="cp_start")
    async def btn_start(self, interaction: discord.Interaction, button: ui.Button):
        # We check permission manually since @has_role doesn't apply to UI buttons directly
        if not await self._check_perm(interaction, "start"): return
        await interaction.response.defer(ephemeral=True)
        # Call the existing logic or the cog method
        mgmt = self.bot.get_cog("Management")
        if mgmt:
            # We mock the interaction flow or just call the logic
            await interaction.followup.send("⏳ Starting server...", ephemeral=True)
            success, message = await self.bot.server.start()
            if success:
                from src.server_info_manager import ServerInfoManager
                await ServerInfoManager(self.bot).update_info(interaction.guild)
                await interaction.edit_original_response(content=f"✅ {message}")
            else:
                await interaction.edit_original_response(content=f"❌ **Error:** {message}")

    @ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="🛑", custom_id="cp_stop")
    async def btn_stop(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_perm(interaction, "stop"): return
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("⏳ Stopping server...", ephemeral=True)
        success, message = await self.bot.server.stop()
        if success:
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
            await interaction.edit_original_response(content=f"✅ {message}")
        else:
            await interaction.edit_original_response(content=f"❌ **Error:** {message}")

    @ui.button(label="Restart", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="cp_restart")
    async def btn_restart(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_perm(interaction, "restart"): return
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("⏳ Restarting server...", ephemeral=True)
        success, message = await self.bot.server.restart()
        if success:
            from src.server_info_manager import ServerInfoManager
            await ServerInfoManager(self.bot).update_info(interaction.guild)
            await interaction.edit_original_response(content=f"✅ {message}")
        else:
            await interaction.edit_original_response(content=f"❌ **Error:** {message}")

    @ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="cp_status")
    async def btn_status(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_perm(interaction, "status"): return
        await interaction.response.defer(ephemeral=True)
        try:
            embed = discord.Embed(title="Minecraft Server Status")
            if self.bot.server.is_running():
                embed.color = 0x57F287
                try:
                    players_response = await rcon_cmd("list")
                    embed.add_field(name="Status", value="🟢 **Online**", inline=False)
                    embed.add_field(name="Players", value=f"```{players_response}```", inline=False)
                except Exception as e:
                    embed.add_field(name="Status", value="🟢 **Online**", inline=False)
                    embed.add_field(name="Players", value="```Unable to fetch player list```", inline=False)
            else:
                embed.color = 0xED4245
                embed.add_field(name="Status", value="🔴 **Offline**", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Status btn error: {e}")
            await interaction.followup.send("❌ Error fetching status.", ephemeral=True)

    async def _check_perm(self, interaction: discord.Interaction, cmd_name: str) -> bool:
        """Helper to verify roles using config map."""
        # Need to re-implement has_role logic for interactions not bound to a command
        if interaction.user.id == config.OWNER_ID:
            return True
        if interaction.user.guild_permissions.administrator:
            return True
            
        has_perm = False
        user_roles = [str(r.id) for r in getattr(interaction.user, 'roles', [])]
        for role_id, allowed_cmds in config.ROLES.items():
            if str(role_id) in user_roles and cmd_name in allowed_cmds:
                has_perm = True
                break
                
        if not has_perm:
            await interaction.response.send_message("❌ You lack the permission to use this button.", ephemeral=True)
        return has_perm


class ControlPanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_id = None
        self.control_panel_task.start()

    def cog_unload(self):
        self.control_panel_task.cancel()

    @tasks.loop(minutes=2)
    async def control_panel_task(self):
        """Periodically ensures the control panel exists and is updated."""
        await self.update_panel()

    @control_panel_task.before_loop
    async def before_task(self):
        await self.bot.wait_until_ready()

    async def update_panel(self):
        channel_id = config.COMMAND_CHANNEL_ID
        if not channel_id: return
        channel = self.bot.get_channel(int(channel_id))
        if not channel: return

        embed = discord.Embed(
            title="🎛️ Server Control Panel",
            description="Use the buttons below to manage the Minecraft Server.",
            color=0x5865F2
        )
        
        status_text = "🟢 **Online**" if self.bot.server.is_running() else "🔴 **Offline**"
        embed.add_field(name="Current Status", value=status_text)
        from datetime import datetime
        embed.set_footer(text=f"Auto-updates • Last checked: {datetime.now().strftime('%H:%M:%S')}")

        view = ControlPanelView(self.bot)

        # Try to find the existing message or send a new one
        if self.message_id:
            try:
                msg = await channel.fetch_message(self.message_id)
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                self.message_id = None # Message was deleted or unreachable

        # If we got here, we need to send a new message
        # Let's delete previous messages from bot in this channel to keep it clean maybe?
        # A simple wipe of bot messages if we want a pure command channel:
        try:
            async for old_msg in channel.history(limit=20):
                if old_msg.author == self.bot.user and old_msg.id != self.message_id and "Control Panel" in str(old_msg.embeds[0].title if old_msg.embeds else ""):
                    await old_msg.delete()
        except: pass

        try:
            new_msg = await channel.send(embed=embed, view=view)
            self.message_id = new_msg.id
        except Exception as e:
            logger.error(f"Failed to send Control Panel: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent view
        self.bot.add_view(ControlPanelView(self.bot))


async def setup(bot):
    await bot.add_cog(ControlPanelCog(bot))
