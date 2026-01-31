"""
Simplified setup views - ONE modal approach
User fills one form → Installation starts immediately
"""

import discord
from discord import ui
from src.mc_installer import mc_installer
from src.logger import logger
from src.config import config


class SimpleSetupModal(ui.Modal, title="🔧 Minecraft Server Setup"):
    """Single comprehensive modal - all settings in one place"""
    
    platform = ui.TextInput(
        label="Platform (paper/vanilla/fabric)",
        placeholder="paper",
        default="paper",
        max_length=10,
        required=False
    )
    
    version = ui.TextInput(
        label="Version (leave empty for latest)",
        placeholder="1.20.4 or leave blank for latest",
        required=False,
        max_length=10
    )
    
    difficulty = ui.TextInput(
        label="Difficulty (peaceful/easy/normal/hard)",
        placeholder="normal",
        default="normal",
        max_length=10,
        required=False
    )
    
    max_players = ui.TextInput(
        label="Max Players (1-100)",
        placeholder="20",
        default="20",
        max_length=3,
        required=False
    )
    
    ram = ui.TextInput(
        label="RAM in GB (1-32)",
        placeholder="4",
        default="4",
        max_length=2,
        required=False
    )
    
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse and validate inputs
            platform = (self.platform.value or "paper").lower().strip()
            if platform not in ["paper", "vanilla", "fabric"]:
                await interaction.response.send_message(
                    "❌ Invalid platform. Use: paper, vanilla, or fabric", 
                    ephemeral=True
                )
                return
            
            version = (self.version.value or "").strip()
            
            difficulty = (self.difficulty.value or "normal").lower().strip()
            if difficulty not in ["peaceful", "easy", "normal", "hard"]:
                await interaction.response.send_message(
                    "❌ Invalid difficulty. Use: peaceful, easy, normal, or hard", 
                    ephemeral=True
                )
                return
            
            try:
                max_players = int(self.max_players.value or "20")
                if not 1 <= max_players <= 100:
                    raise ValueError()
            except ValueError:
                await interaction.response.send_message(
                    "❌ Max players must be a number between 1 and 100", 
                    ephemeral=True
                )
                return
            
            try:
                ram = int(self.ram.value or "4")
                if not 1 <= ram <= 32:
                    raise ValueError()
            except ValueError:
                await interaction.response.send_message(
                    "❌ RAM must be a number between 1 and 32", 
                    ephemeral=True
                )
                return
            
            # Build config with validated values + sane defaults
            setup_config = {
                'platform': platform,
                'version': version or "latest",
                'difficulty': difficulty,
                'max_players': max_players,
                'whitelist': False,  # Default
                'online_mode': True,  # Default
                'view_distance': 16,  # Default
                'seed': "",  # Random
                'max_ram': ram,
                'min_ram': max(1, ram // 2)  # Half of max RAM
            }
            
            # Update global config for RAM
            config.JAVA_XMX = f"{ram}G"
            config.JAVA_XMS = f"{max(1, ram // 2)}G"
            
            # Start installation immediately (no confirmation)
            await self.start_installation(interaction, setup_config)
            
        except Exception as e:
            logger.error(f"Setup modal error: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {e}", 
                ephemeral=True
            )
    
    async def start_installation(self, interaction: discord.Interaction, setup_config: dict):
        """Start installation and show progress in ONE message"""
        
        # Create initial progress embed
        embed = discord.Embed(
            title="⏳ Installing Minecraft Server",
            description="**Step 1/5:** Preparing installation...",
            color=0xFEE75C  # Yellow
        )
        embed.add_field(
            name="📋 Configuration",
            value=(
                f"**Platform:** {setup_config['platform'].title()}\n"
                f"**Version:** {setup_config['version']}\n"
                f"**Difficulty:** {setup_config['difficulty'].title()}\n"
                f"**Max Players:** {setup_config['max_players']}\n"
                f"**RAM:** {setup_config['min_ram']}G - {setup_config['max_ram']}G"
            ),
            inline=False
        )
        
        # Send initial message
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # STEP 1: Discord Structure Setup
        from src.setup_helper import SetupHelper
        
        try:
            embed.description = "**Step 1/5:** Creating Discord channels and roles..."
            await message.edit(embed=embed)
            
            setup_helper = SetupHelper(interaction.client)
            updates = await setup_helper.ensure_setup(interaction.guild)
            
            # Update config
            config.update_dynamic_config(updates)
            await self._save_config_to_file(updates)
            
            logger.info(f"Discord setup completed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Discord setup failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ Discord setup failed: {e}"
            await message.edit(embed=embed)
            return
        
        # STEP 2: Download server
        try:
            embed.description = f"**Step 2/5:** Downloading {setup_config['platform'].title()} server..."
            await message.edit(embed=embed)
            
            # Get version if "latest"
            if setup_config['version'] == 'latest':
                setup_config['version'] = await mc_installer.get_latest_version(setup_config['platform'])
            
            async def progress_callback(msg):
                embed.description = f"**Step 2/5:** {msg}"
                try:
                    await message.edit(embed=embed)
                except:
                    pass
            
            success, result = await mc_installer.download_server(
                setup_config['platform'],
                setup_config['version'],
                progress_callback
            )
            
            if not success:
                raise Exception(result)
            
        except Exception as e:
            logger.error(f"Server download failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ Download failed: {e}"
            await message.edit(embed=embed)
            return
        
        # STEP 3: Accept EULA
        try:
            embed.description = "**Step 3/5:** Accepting Minecraft EULA..."
            await message.edit(embed=embed)
            
            await mc_installer.accept_eula()
            
        except Exception as e:
            logger.error(f"EULA acceptance failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ EULA failed: {e}"
            await message.edit(embed=embed)
            return
        
        # STEP 4: Configure server
        try:
            embed.description = "**Step 4/5:** Configuring server settings..."
            await message.edit(embed=embed)
            
            await mc_installer.configure_server_properties(setup_config)
            
        except Exception as e:
            logger.error(f"Server configuration failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ Configuration failed: {e}"
            await message.edit(embed=embed)
            return
        
        # STEP 5: Complete!
        embed.description = "**Step 5/5:** Finalizing setup..."
        await message.edit(embed=embed)
        
        # Success embed
        command_channel = interaction.client.get_channel(config.COMMAND_CHANNEL_ID)
        
        embed = discord.Embed(
            title="✅ Installation Complete!",
            description="Your Minecraft server is ready to launch!",
            color=0x57F287  # Green
        )
        
        embed.add_field(
            name="🚀 Quick Start",
            value=(
                f"1. Go to {command_channel.mention if command_channel else '#command'}\n"
                f"2. Run `/start` to launch the server\n"
                f"3. Wait for world generation (first start takes time)\n"
                f"4. Use `/status` to check when it's online"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use /help to see all available commands")
        
        await message.edit(embed=embed)
    
    async def _save_config_to_file(self, updates: dict):
        """Save configuration updates to bot_config.json file"""
        import json
        try:
            # Load/Update bot_config.json
            with open('bot_config.json', 'r') as f:
                config_data = json.load(f)
            
            if 'command_channel_id' in updates:
                config_data['command_channel_id'] = updates['command_channel_id']
            if 'log_channel_id' in updates:
                config_data['log_channel_id'] = updates['log_channel_id']
            if 'debug_channel_id' in updates:
                config_data['debug_channel_id'] = updates['debug_channel_id']
            if 'guild_id' in updates:
                config_data['guild_id'] = updates['guild_id']
            
            # Roles are no longer saved to config (managed by user via permissions in user_config.json)
            
            with open('bot_config.json', 'w') as f:
                json.dump(config_data, f, indent='\t')
                f.write('\n')
            
            logger.info("config.json updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update config.json: {e}")
            raise
