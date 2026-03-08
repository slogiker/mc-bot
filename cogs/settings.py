import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
from src.config import config
from src.utils import has_role, send_debug

logger = logging.getLogger('mc_bot')

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Java RAM Settings", description="Modify minimum and maximum RAM allocation", emoji="💾", value="ram"),
            discord.SelectOption(label="Schedules", description="Modify backup and restart times", emoji="⏰", value="schedules"),
            discord.SelectOption(label="Timezone", description="Configure your local timezone", emoji="🌍", value="timezone"),
            discord.SelectOption(label="Role Permissions", description="Edit which roles can use specific commands", emoji="🛡️", value="permissions")
        ]
        super().__init__(placeholder="Select a setting category to edit...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "ram":
            await interaction.response.send_modal(RamModal())
        elif category == "schedules":
            await interaction.response.send_modal(ScheduleModal())
        elif category == "timezone":
            await interaction.response.send_modal(TimezoneModal())
        elif category == "permissions":
            await interaction.response.send_modal(PermissionsModal())

class SettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(CategorySelect())

class RamModal(discord.ui.Modal, title='Java RAM Configuration'):
    def __init__(self):
        super().__init__()
        user_config = config.load_user_config()
        
        self.min_ram = discord.ui.TextInput(
            label='Minimum RAM (Xms)',
            style=discord.TextStyle.short,
            placeholder='e.g., 2G',
            default=user_config.get('java_ram_min', '2G'),
            required=True,
            max_length=6
        )
        self.max_ram = discord.ui.TextInput(
            label='Maximum RAM (Xmx)',
            style=discord.TextStyle.short,
            placeholder='e.g., 4G',
            default=user_config.get('java_ram_max', '4G'),
            required=True,
            max_length=6
        )
        
        self.add_item(self.min_ram)
        self.add_item(self.max_ram)

    async def on_submit(self, interaction: discord.Interaction):
        user_config = config.load_user_config()
        user_config['java_ram_min'] = self.min_ram.value
        user_config['java_ram_max'] = self.max_ram.value
        
        # Save to disk
        config.save_user_config(user_config)
        # Apply to running memory
        config.JAVA_XMS = self.min_ram.value
        config.JAVA_XMX = self.max_ram.value
        
        await interaction.response.send_message(f"✅ RAM settings updated. Min: `{self.min_ram.value}`, Max: `{self.max_ram.value}`.\n*These changes will apply the next time the Minecraft server starts.*", ephemeral=True)
        await send_debug(interaction.client, f"Settings updated by {interaction.user}: RAM Min={self.min_ram.value}, Max={self.max_ram.value}")

class ScheduleModal(discord.ui.Modal, title='Schedule Configuration'):
    def __init__(self):
        super().__init__()
        user_config = config.load_user_config()
        
        self.backup_time = discord.ui.TextInput(
            label='Daily Backup Time (24h format)',
            style=discord.TextStyle.short,
            placeholder='e.g., 03:00',
            default=user_config.get('backup_time', '03:00'),
            required=True,
            max_length=5
        )
        self.restart_time = discord.ui.TextInput(
            label='Daily Restart Time (24h format)',
            style=discord.TextStyle.short,
            placeholder='e.g., 04:00',
            default=user_config.get('restart_time', '04:00'),
            required=True,
            max_length=5
        )
        self.retention = discord.ui.TextInput(
            label='Backup Retention (Days to keep)',
            style=discord.TextStyle.short,
            placeholder='e.g., 7',
            default=str(user_config.get('backup_keep_days', 7)),
            required=True,
            max_length=3
        )
        
        self.add_item(self.backup_time)
        self.add_item(self.restart_time)
        self.add_item(self.retention)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate time format loosely
        if ":" not in self.backup_time.value or ":" not in self.restart_time.value:
            await interaction.response.send_message("❌ Invalid time format. Please use HH:MM (e.g., 14:30).", ephemeral=True)
            return
            
        try:
            retention_days = int(self.retention.value)
        except ValueError:
            await interaction.response.send_message("❌ Retention days must be a number.", ephemeral=True)
            return

        user_config = config.load_user_config()
        user_config['backup_time'] = self.backup_time.value
        user_config['restart_time'] = self.restart_time.value
        user_config['backup_keep_days'] = retention_days
        
        # Save to disk
        config.save_user_config(user_config)
        # Apply to running memory
        config.BACKUP_TIME = self.backup_time.value
        config.RESTART_TIME = self.restart_time.value
        config.BACKUP_RETENTION_DAYS = retention_days
        
        await interaction.response.send_message(
            f"✅ Schedules updated.\nBackup: `{self.backup_time.value}`\nRestart: `{self.restart_time.value}`\nRetention: `{retention_days} days`.\n"
            f"*Restart the bot to apply the new schedule times.*", ephemeral=True)
        await send_debug(interaction.client, f"Settings updated by {interaction.user}: Backup={self.backup_time.value}, Restart={self.restart_time.value}")

class TimezoneModal(discord.ui.Modal, title='Timezone Configuration'):
    def __init__(self):
        super().__init__()
        user_config = config.load_user_config()
        
        self.tz = discord.ui.TextInput(
            label='Timezone (e.g. Europe/London or auto)',
            style=discord.TextStyle.short,
            placeholder='e.g., America/New_York',
            default=user_config.get('timezone', 'auto'),
            required=True,
            max_length=50
        )
        self.add_item(self.tz)

    async def on_submit(self, interaction: discord.Interaction):
        from pytz import all_timezones
        
        tz_val = self.tz.value.strip()
        if tz_val.lower() != 'auto' and tz_val not in all_timezones:
             await interaction.response.send_message(f"❌ Invalid timezone: `{tz_val}`. Must be a valid IANA timezone name or 'auto'.", ephemeral=True)
             return

        user_config = config.load_user_config()
        user_config['timezone'] = tz_val
        
        # Save to disk
        config.save_user_config(user_config)
        
        # Apply to running memory (if auto, config.py resolves it on load, but we'll re-resolve it here)
        if tz_val.lower() == 'auto':
            try:
                import urllib.request
                with urllib.request.urlopen("http://ip-api.com/json/", timeout=3) as response:
                    config.TIMEZONE = json.loads(response.read().decode()).get('timezone', 'UTC')
            except:
                config.TIMEZONE = 'UTC'
        else:
            config.TIMEZONE = tz_val
            
        await interaction.response.send_message(f"✅ Timezone updated to: `{config.TIMEZONE}` (Input: `{tz_val}`).", ephemeral=True)
        await send_debug(interaction.client, f"Settings updated by {interaction.user}: Timezone={tz_val}")

class PermissionsModal(discord.ui.Modal, title='Role Permissions Edit'):
    def __init__(self):
        super().__init__()
        user_config = config.load_user_config()
        perms = user_config.get('permissions', {})
        
        # We can't fit all arrays perfectly into TextInputs, so we use a comma-separated format
        owner_cmds = ", ".join(perms.get("Owner", []))
        admin_cmds = ", ".join(perms.get("Admin", []))
        player_cmds = ", ".join(perms.get("Player", []))
        everyone_cmds = ", ".join(perms.get("@everyone", []))
        
        self.owner_input = discord.ui.TextInput(
            label='Owner Commands (Comma separated)',
            style=discord.TextStyle.paragraph,
            default=owner_cmds,
            required=True
        )
        self.admin_input = discord.ui.TextInput(
            label='Admin Commands',
            style=discord.TextStyle.paragraph,
            default=admin_cmds,
            required=True
        )
        self.player_input = discord.ui.TextInput(
            label='Player Commands',
            style=discord.TextStyle.paragraph,
            default=player_cmds,
            required=True
        )
        self.everyone_input = discord.ui.TextInput(
            label='@everyone Commands',
            style=discord.TextStyle.paragraph,
            default=everyone_cmds,
            required=True
        )
        
        self.add_item(self.owner_input)
        self.add_item(self.admin_input)
        self.add_item(self.player_input)
        self.add_item(self.everyone_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_config = config.load_user_config()
        
        # Clean up the comma separated lists back into python lists
        def parse_cmds(raw_str):
            return [c.strip() for c in raw_str.split(',') if c.strip()]
            
        new_perms = {
            "Owner": parse_cmds(self.owner_input.value),
            "Admin": parse_cmds(self.admin_input.value),
            "Player": parse_cmds(self.player_input.value),
            "@everyone": parse_cmds(self.everyone_input.value)
        }
        
        user_config['permissions'] = new_perms
        config.save_user_config(user_config)
        
        # Apply to live memory
        config.ROLE_PERMISSIONS = new_perms
        
        # We need to re-resolve the guild roles to IDs
        if interaction.guild:
            config.resolve_role_permissions(interaction.guild)
            
        await interaction.response.send_message(f"✅ Permissions mapped and updated in memory.", ephemeral=True)
        await send_debug(interaction.client, f"Settings updated by {interaction.user}: Role Permissions adjusted")

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Interactive GUI to modify Bot and Server configurations")
    @has_role("cmd") # Owner/Admin role
    async def settings(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Control Panel Settings",
            description="Use the dropdown below to select which configuration category you would like to edit.\n\n"
                        "**Categories Available:**\n"
                        "💾 **Java RAM:** Server memory allocation\n"
                        "⏰ **Schedules:** Automated backup and restart times\n"
                        "🌍 **Timezone:** Regional time settings\n"
                        "🛡️ **Permissions:** Edit commands allowed per Role",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=SettingsView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(SettingsCog(bot))
