import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import os
from src.config import config
from src.utils import has_role, send_debug, rcon_cmd

logger = logging.getLogger('mc_bot')

class PlayerManageSelect(discord.ui.Select):
    def __init__(self, players, action_type):
        self.action_type = action_type
        options = []
        for p in players[:25]:
            desc = f"UUID: {p.get('uuid', 'Unknown')}" if 'uuid' in p else ""
            options.append(discord.SelectOption(label=p.get('name', 'Unknown'), description=desc, value=p.get('name', 'Unknown')))
            
        placeholder = f"Select a player to {action_type}..."
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        cmd = ""
        success_msg = ""
        
        if self.action_type == "Kick":
            cmd = f"kick {target} Kicked by Admin via Discord"
            success_msg = f"🥾 Kicked `{target}`"
        elif self.action_type == "Ban":
            cmd = f"ban {target} Banned by Admin via Discord"
            success_msg = f"🔨 Banned `{target}`"
        elif self.action_type == "Pardon":
            cmd = f"pardon {target}"
            success_msg = f"🕊️ Pardoned `{target}`"
        elif self.action_type == "Whitelist Add":
            cmd = f"whitelist add {target}"
            success_msg = f"✅ Added `{target}` to whitelist"
        elif self.action_type == "Whitelist Remove":
            cmd = f"whitelist remove {target}"
            success_msg = f"❌ Removed `{target}` from whitelist"
        elif self.action_type == "Op":
            cmd = f"op {target}"
            success_msg = f"👑 Opped `{target}`"
        elif self.action_type == "Deop":
            cmd = f"deop {target}"
            success_msg = f"🔻 Deopped `{target}`"

        await interaction.response.defer(ephemeral=True)
        resp = await rcon_cmd(cmd)
        
        if "Unknown command" in resp or "Error" in resp:
             await interaction.followup.send(f"⚠️ RCON responded with an error:\n`{resp}`", ephemeral=True)
        else:
             # Reload whitelist/ops if needed
             if "whitelist" in cmd:
                 await rcon_cmd("whitelist reload")
             await interaction.followup.send(f"{success_msg}\n*RCON:* `{resp}`", ephemeral=True)
             await send_debug(interaction.client, f"Player Manager: {interaction.user} executed '{cmd}'")

class PlayerActionView(discord.ui.View):
    def __init__(self, action_type, player_list):
        super().__init__(timeout=600)
        if not player_list:
            self.add_item(discord.ui.Button(label="No players available for this action", disabled=True))
        else:
            self.add_item(PlayerManageSelect(player_list, action_type))

class MainPlayerView(discord.ui.View):
    def __init__(self, data_cache):
        super().__init__(timeout=600)
        self.data_cache = data_cache

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.secondary, emoji="🥾")
    async def btn_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Can only kick online players or anyone in usercache
        players = self.data_cache.get('usercache', [])
        await interaction.response.send_message("Select player to kick:", view=PlayerActionView("Kick", players), ephemeral=True)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, emoji="🔨")
    async def btn_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = self.data_cache.get('usercache', [])
        await interaction.response.send_message("Select player to ban:", view=PlayerActionView("Ban", players), ephemeral=True)

    @discord.ui.button(label="Pardon", style=discord.ButtonStyle.success, emoji="🕊️")
    async def btn_pardon(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = self.data_cache.get('banned', [])
        await interaction.response.send_message("Select player to pardon (unban):", view=PlayerActionView("Pardon", players), ephemeral=True)

    @discord.ui.button(label="Whitelist Add", style=discord.ButtonStyle.primary, emoji="✅")
    async def btn_wl_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We don't have a list of all non-whitelisted players, so we use a Modal for manual entry
        await interaction.response.send_modal(ManualEntryModal("Whitelist Add", "whitelist add {target}"))

    @discord.ui.button(label="Whitelist Remove", style=discord.ButtonStyle.danger, emoji="❌")
    async def btn_wl_rem(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = self.data_cache.get('whitelist', [])
        await interaction.response.send_message("Select player to remove from whitelist:", view=PlayerActionView("Whitelist Remove", players), ephemeral=True)

    @discord.ui.button(label="Op", style=discord.ButtonStyle.primary, emoji="👑")
    async def btn_op(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ManualEntryModal("Op", "op {target}"))

    @discord.ui.button(label="Deop", style=discord.ButtonStyle.secondary, emoji="🔻")
    async def btn_deop(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = self.data_cache.get('ops', [])
        await interaction.response.send_message("Select player to remove Op status:", view=PlayerActionView("Deop", players), ephemeral=True)

class ManualEntryModal(discord.ui.Modal):
    def __init__(self, title_text, cmd_template):
        super().__init__(title=title_text)
        self.cmd_template = cmd_template
        
        self.target_name = discord.ui.TextInput(
            label='Player Name',
            style=discord.TextStyle.short,
            placeholder='e.g., Notch',
            required=True,
            max_length=30
        )
        self.add_item(self.target_name)

    async def on_submit(self, interaction: discord.Interaction):
        cmd = self.cmd_template.replace("{target}", self.target_name.value)
        await interaction.response.defer(ephemeral=True)
        resp = await rcon_cmd(cmd)
        
        if "whitelist" in cmd:
             await rcon_cmd("whitelist reload")
             
        await interaction.followup.send(f"Executed: `{cmd}`\n*RCON:* `{resp}`", ephemeral=True)
        await send_debug(interaction.client, f"Player Manager: {interaction.user} executed '{cmd}'")


class PlayersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _read_json_safe(self, filename):
        filepath = os.path.join(config.SERVER_DIR, filename)
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    @app_commands.command(name="players_manage", description="Interactive GUI to manage Bans, Whitelists, and Ops")
    @has_role("players") # Owner/Admin
    async def players_manage(self, interaction: discord.Interaction):
        # Build cache
        data_cache = {
            'whitelist': self._read_json_safe('whitelist.json'),
            'ops': self._read_json_safe('ops.json'),
            'banned': self._read_json_safe('banned-players.json'),
            'usercache': self._read_json_safe('usercache.json') # Master list of known players
        }
        
        wl_count = len(data_cache['whitelist'])
        op_count = len(data_cache['ops'])
        ban_count = len(data_cache['banned'])
        
        embed = discord.Embed(
            title="👥 Player Management",
            description="Use the buttons below to moderate your server.\n"
                        "⚠️ *Note: The server must be online for commands to take effect immediately.*",
            color=discord.Color.gold()
        )
        embed.add_field(name="Whitelisted", value=f"{wl_count} players", inline=True)
        embed.add_field(name="Operators", value=f"{op_count} players", inline=True)
        embed.add_field(name="Banned", value=f"{ban_count} players", inline=True)
        
        await interaction.response.send_message(embed=embed, view=MainPlayerView(data_cache), ephemeral=True)

async def setup(bot):
    await bot.add_cog(PlayersCog(bot))
