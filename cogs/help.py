import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.logger import logger

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Displays commands you can use based on your roles")
    async def help(self, interaction: discord.Interaction):
        try:
            # Get user's role IDs/names
            user_roles = [role.name for role in interaction.user.roles]
            user_roles.append("@everyone")
            
            # Get permissions the user is allowed to use
            allowed_permissions = set()
            for role_name in user_roles:
                if role_name in config.ROLE_PERMISSIONS:
                    allowed_permissions.update(config.ROLE_PERMISSIONS[role_name])
            
            # Check if the user has permission to use the given command
            # This involves checking direct command name access via ROLE_PERMISSIONS
            # or checking custom _required_permission attributes set on command checks.
            def can_use(cmd):
                # Check /help specifically
                if cmd.name == "help":
                    return True
                
                # Check name
                if cmd.name in allowed_permissions:
                    return True
                
                # Check checks for _required_permission
                for check in cmd.checks:
                    if hasattr(check, "_required_permission"):
                        if check._required_permission in allowed_permissions:
                            return True
                return False

            # Define categories
            category_map = {
                "🎮 Server Controls": ["control", "start", "stop", "restart", "status", "kill"],
                "ℹ️ Server Information": ["info", "players", "version", "seed", "mods", "uptime", "ip"],
                "🛠️ Administration": ["setup", "cmd", "backup", "backup_list", "backup_download", "logs", "whitelist_add", "set_spawn", "sync", "reload_config", "bot_restart", "players_manage", "settings", "mod_search", "update"],
                "📊 Statistics": ["stats"],
                "📅 Events": ["event_create", "event_list", "event_delete"],
                "🤖 Automation": ["trigger_add", "trigger_list", "trigger_remove"],
                "🔗 Linking": ["link", "verify", "unlink", "linked", "unlink_admin"]
            }
            
            # Inverse map for easy lookup
            cmd_to_cat = {}
            for cat, cmds in category_map.items():
                for c in cmds:
                    cmd_to_cat[c] = cat

            categorized_output = {cat: [] for cat in category_map.keys()}
            uncategorized = []

            for cmd in self.bot.tree.walk_commands():
                if isinstance(cmd, app_commands.Group):
                    continue # Skip groups themselves, we want subcommands
                
                if not can_use(cmd):
                    continue
                
                # Use qualified name for groups (e.g., "playit claim")
                full_name = cmd.qualified_name
                desc = cmd.description or "No description"
                cmd_text = f"**/{full_name}** - {desc}\n"
                
                # Decide category
                cat = cmd_to_cat.get(cmd.name) # Try top-level name first
                if not cat and " " in full_name:
                    cat = cmd_to_cat.get(full_name.split()[0]) # Try group name (e.g. "playit")
                
                if cat:
                    categorized_output[cat].append((full_name, cmd_text))
                else:
                    if cmd.name != "help":
                        uncategorized.append((full_name, cmd_text))
            
            # Create embed
            embed = discord.Embed(title="🤖 Bot Commands", description="Here are the commands you can use:", color=0x5865F2)
            
            total_cmds = 0
            for cat_name in category_map.keys():
                cmds = categorized_output[cat_name]
                if cmds:
                    cmds.sort() # Alphabetical sort
                    cat_text = "".join(c[1] for c in cmds)
                    embed.add_field(name=cat_name, value=cat_text, inline=False)
                    total_cmds += len(cmds)
            
            if uncategorized:
                uncategorized.sort()
                embed.add_field(name="📦 Other", value="".join(c[1] for c in uncategorized), inline=False)
                total_cmds += len(uncategorized)
            
            if total_cmds == 0:
                embed.description = "You don't have permission to use any commands."
            
            embed.set_footer(text="Use /help to see this menu again")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            error_msg = f"❌ Failed to show help: {e}"
            logger.error(error_msg)
            await interaction.response.send_message(error_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))
