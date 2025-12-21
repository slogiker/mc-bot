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
            # Get user's role IDs
            user_role_ids = [str(role.id) for role in interaction.user.roles]
            # Get commands the user is allowed to use
            allowed_commands = set()
            for role_id in user_role_ids:
                if role_id in config.ROLES:
                    allowed_commands.update(config.ROLES[role_id])
            
            # Create embed with filtered commands
            embed = discord.Embed(title="Bot Commands", description="Commands you can use:")
            
            count = 0
            for cmd in self.bot.tree.get_commands():
                if cmd.name in allowed_commands or cmd.name == "help":  # Always show /help
                    embed.add_field(name=f"/{cmd.name}", value=cmd.description, inline=False)
                    count += 1
            
            if count == 0:
                embed.add_field(name="No Commands", value="You don't have permission to use any commands.", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            error_msg = f"❌ Failed to show help: {e}"
            logger.error(error_msg)
            await interaction.response.send_message(error_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))
