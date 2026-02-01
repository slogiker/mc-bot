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
            
            # Get commands the user is allowed to use
            allowed_commands = set()
            for role_name in user_roles:
                if role_name in config.ROLE_PERMISSIONS:
                    allowed_commands.update(config.ROLE_PERMISSIONS[role_name])
            
            # Define categories
            categories = {
                "🎮 Server Controls": ["control", "start", "stop", "restart", "status"],
                "ℹ️ Server Information": ["info", "players", "version", "seed", "mods"],
                "🛠️ Administration": ["setup", "cmd", "backup_now", "logs", "whitelist_add", "set_spawn"],
                "📊 Statistics": ["stats"]
            }
            
            # Create embed
            embed = discord.Embed(title="🤖 Bot Commands", description="Here are the commands you can use:", color=0x5865F2)
            
            total_cmds = 0
            
            for cat_name, cmd_names in categories.items():
                cat_text = ""
                for name in cmd_names:
                    # Check if user has permission and command exists
                    cmd = self.bot.tree.get_command(name)
                    if cmd and (name in allowed_commands or name == "help"):
                        cat_text += f"**/{name}** - {cmd.description}\n"
                        total_cmds += 1
                
                if cat_text:
                    embed.add_field(name=cat_name, value=cat_text, inline=False)
            
            # Handle commands not in categories (if any)
            all_categorized = set(c for cmds in categories.values() for c in cmds)
            uncategorized = ""
            for cmd in self.bot.tree.get_commands():
                if cmd.name not in all_categorized and cmd.name != "help":
                     if cmd.name in allowed_commands:
                        uncategorized += f"**/{cmd.name}** - {cmd.description}\n"
            
            if uncategorized:
                embed.add_field(name="📦 Other", value=uncategorized, inline=False)
            
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
