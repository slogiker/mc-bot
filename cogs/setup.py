import discord
from discord import app_commands
from discord.ext import commands
from src.config import config
from src.logger import logger
from src.setup_helper import SetupHelper
import json

class Setup(commands.Cog):
    """Discord server setup commands for Minecraft bot"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Set up Discord channels and server structure")
    async def setup(self, interaction: discord.Interaction):
        """
        Manually trigger Discord server setup.
        Creates category, channels, roles and updates configuration.
        In dry-run mode, shows what would be created without making changes.
        """
        # Check permissions - user must have administrator or be server owner
        if not interaction.user.guild_permissions.administrator and interaction.user != interaction.guild.owner:
            await interaction.response.send_message(
                "❌ You need Administrator permissions to run this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)
        
        # Check if in dry-run mode
        if config.DRY_RUN_MODE:
            await self._dry_run_setup(interaction)
            return
        
        # Create embed for setup progress
        embed = discord.Embed(
            title="🔧 Minecraft Server Setup",
            description="Setting up Discord server structure...",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="⏳ Starting setup...", inline=False)
        
        await interaction.followup.send(embed=embed)
        
        try:
            # Run setup using SetupHelper
            setup_helper = SetupHelper(self.bot)
            updates = await setup_helper.ensure_setup(interaction.guild)
            
            # Update in-memory config
            config.update_dynamic_config(updates)
            
            # Save to config.json
            await self._save_config_to_file(updates)
            
            # Update embed with success
            embed.color = discord.Color.green()
            embed.title = "✅ Setup Complete!"
            embed.clear_fields()
            
            # Show what was created/found
            category_found = discord.utils.get(interaction.guild.categories, name="Minecraft Server")
            command_channel = self.bot.get_channel(config.COMMAND_CHANNEL_ID)
            log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            debug_channel = self.bot.get_channel(config.DEBUG_CHANNEL_ID)
            
            structure_info = []
            if category_found:
                structure_info.append(f"📁 Category: {category_found.mention}")
            if command_channel:
                structure_info.append(f"💬 Commands: {command_channel.mention}")
            if log_channel:
                structure_info.append(f"📜 Logs: {log_channel.mention}")
            if debug_channel:
                structure_info.append(f"🐛 Debug: {debug_channel.mention}")
            
            embed.add_field(
                name="Discord Structure",
                value="\n".join(structure_info) if structure_info else "✅ All channels configured",
                inline=False
            )
            
            # Show roles
            roles_info = []
            for role in interaction.guild.roles:
                if role.name in ["MC Admin", "MC Player"]:
                    roles_info.append(f"👥 {role.mention}")
            
            if roles_info:
                embed.add_field(
                    name="Roles Created",
                    value="\n".join(roles_info),
                    inline=False
                )
            
            # Next steps
            next_steps = (
                "**Next Steps:**\n"
                "1. ✅ Discord structure is ready!\n"
                "2. 📦 Install Minecraft server (coming soon)\n"
                "3. 🎮 Configure server settings\n"
                "4. 🚀 Start playing!\n\n"
                f"Use commands in {command_channel.mention if command_channel else '#command channel'}"
            )
            embed.add_field(name="What's Next?", value=next_steps, inline=False)
            
            await interaction.edit_original_response(embed=embed)
            
            # Send confirmation to debug channel
            if debug_channel:
                debug_embed = discord.Embed(
                    title="🔧 Setup Completed",
                    description=f"Discord server structure configured by {interaction.user.mention}",
                    color=discord.Color.green()
                )
                debug_embed.add_field(
                    name="Channels Updated",
                    value=f"Command: {command_channel.mention if command_channel else 'N/A'}\n"
                          f"Log: {log_channel.mention if log_channel else 'N/A'}\n"
                          f"Debug: {debug_channel.mention}",
                    inline=False
                )
                await debug_channel.send(embed=debug_embed)
            
            logger.info(f"Setup completed successfully by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Setup failed: {e}", exc_info=True)
            
            # Update embed with error
            embed.color = discord.Color.red()
            embed.title = "❌ Setup Failed"
            embed.clear_fields()
            embed.add_field(
                name="Error",
                value=f"```{str(e)}```",
                inline=False
            )
            embed.add_field(
                name="Troubleshooting",
                value="• Make sure the bot has Administrator permissions\n"
                      "• Check that the bot can create channels and roles\n"
                      "• View logs for more details",
                inline=False
            )
            
            await interaction.edit_original_response(embed=embed)

    async def _dry_run_setup(self, interaction: discord.Interaction):
        """Preview what would be created during setup without making changes"""
        embed = discord.Embed(
            title="🌵 Dry-Run: Discord Server Setup Preview",
            description="This is a preview of what would be created. **No changes will be made.**",
            color=discord.Color.gold()
        )
        
        # Check what already exists
        guild = interaction.guild
        category_exists = discord.utils.get(guild.categories, name="Minecraft Server")
        command_exists = discord.utils.get(guild.text_channels, name="command")
        log_exists = discord.utils.get(guild.text_channels, name="log")
        debug_exists = discord.utils.get(guild.text_channels, name="debug")
        
        admin_role_exists = discord.utils.get(guild.roles, name="MC Admin")
        player_role_exists = discord.utils.get(guild.roles, name="MC Player")
        
        # Category
        if category_exists:
            category_status = f"✓ Exists: {category_exists.mention}"
        else:
            category_status = "➕ Would create category 'Minecraft Server'"
        
        # Channels
        channels_status = []
        if command_exists:
            channels_status.append(f"✓ Exists: {command_exists.mention}")
        else:
            channels_status.append("➕ Would create #command channel")
            
        if log_exists:
            channels_status.append(f"✓ Exists: {log_exists.mention}")
        else:
            channels_status.append("➕ Would create #log channel")
            
        if debug_exists:
            channels_status.append(f"✓ Exists: {debug_exists.mention}")
        else:
            channels_status.append("➕ Would create #debug channel")
        
        # Roles
        roles_status = []
        if admin_role_exists:
            roles_status.append(f"✓ Exists: {admin_role_exists.mention}")
        else:
            roles_status.append("➕ Would create 'MC Admin' role")
            
        if player_role_exists:
            roles_status.append(f"✓ Exists: {player_role_exists.mention}")
        else:
            roles_status.append("➕ Would create 'MC Player' role")
        
        # Build embed
        embed.add_field(
            name="📁 Category",
            value=category_status,
            inline=False
        )
        
        embed.add_field(
            name="💬 Channels",
            value="\n".join(channels_status),
            inline=False
        )
        
        embed.add_field(
            name="👥 Roles",
            value="\n".join(roles_status),
            inline=False
        )
        
        # Config updates
        config_updates = []
        if command_exists:
            config_updates.append(f"• command_channel_id: {command_exists.id}")
        else:
            config_updates.append("• command_channel_id: <new channel ID>")
            
        if log_exists:
            config_updates.append(f"• log_channel_id: {log_exists.id}")
        else:
            config_updates.append("• log_channel_id: <new channel ID>")
            
        if debug_exists:
            config_updates.append(f"• debug_channel_id: {debug_exists.id}")
        else:
            config_updates.append("• debug_channel_id: <new channel ID>")
        
        embed.add_field(
            name="📝 config.json Updates",
            value="\n".join(config_updates),
            inline=False
        )
        
        # Footer with instructions
        embed.set_footer(
            text="🌵 DRY-RUN MODE: To actually create these, restart bot without --dry-run flag"
        )
        
        await interaction.followup.send(embed=embed)
        logger.info(f"Dry-run setup preview shown to {interaction.user.name}")

    async def _save_config_to_file(self, updates: dict):
        """Save configuration updates to config.json file"""
        try:
            # Read current config
            with open('config.json', 'r') as f:
                config_data = json.load(f)
            
            # Update with new values
            if 'command_channel_id' in updates:
                config_data['command_channel_id'] = updates['command_channel_id']
            if 'log_channel_id' in updates:
                config_data['log_channel_id'] = updates['log_channel_id']
            if 'debug_channel_id' in updates:
                config_data['debug_channel_id'] = updates['debug_channel_id']
            if 'roles' in updates:
                config_data['roles'] = updates['roles']
            
            # Write back
            with open('config.json', 'w') as f:
                json.dump(config_data, f, indent='\t')
                f.write('\n')
            
            logger.info("config.json updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update config.json: {e}")
            raise

async def setup(bot):
    await bot.add_cog(Setup(bot))
