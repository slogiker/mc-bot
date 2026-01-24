"""
New improved setup views with modal-first approach
User fills modal → Confirmation embed → Single confirm button → Setup executes
"""

import discord
from discord import ui
from src.mc_installer import mc_installer
from src.logger import logger
from src.config import config


class SetupConfigModal(ui.Modal, title="🔧 Minecraft Server Setup"):
    """Main setup modal - collects all configuration at once"""
    
    platform = ui.TextInput(
        label="Server Platform",
        placeholder="paper, vanilla, or fabric (default: paper)",
        default="paper",
        max_length=10,
        required=False
    )
    
    version = ui.TextInput(
        label="Minecraft Version",
        placeholder="Leave empty for latest (e.g. 1.20.4)",
        required=False,
        max_length=10
    )
    
    difficulty = ui.TextInput(
        label="Difficulty",
        placeholder="peaceful, easy, normal, or hard (default: normal)",
        default="normal",
        max_length=10,
        required=False
    )
    
    max_players = ui.TextInput(
        label="Max Players",
        placeholder="20",
        default="20",
        max_length=3,
        required=False
    )
    
    whitelist = ui.TextInput(
        label="Enable Whitelist?",
        placeholder="yes or no (default: no)",
        default="no",
        max_length=3,
        required=False
    )
    
    def __init__(self, setup_manager):
        super().__init__()
        self.manager = setup_manager
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse and validate inputs
        try:
            # Platform validation
            platform = (self.platform.value or "paper").lower().strip()
            if platform not in ["paper", "vanilla", "fabric"]:
                await interaction.response.send_message(
                    "❌ Invalid platform. Use: paper, vanilla, or fabric", 
                    ephemeral=True
                )
                return
            
            # Version (empty = latest)
            version = (self.version.value or "").strip()
            
            # Difficulty validation
            difficulty = (self.difficulty.value or "normal").lower().strip()
            if difficulty not in ["peaceful", "easy", "normal", "hard"]:
                await interaction.response.send_message(
                    "❌ Invalid difficulty. Use: peaceful, easy, normal, or hard", 
                    ephemeral=True
                )
                return
            
            # Max players validation
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
            
            # Whitelist parsing
            whitelist_input = (self.whitelist.value or "no").lower().strip()
            whitelist = whitelist_input in ["yes", "y", "true", "1", "on"]
            
            # Store configuration
            self.manager.config = {
                'platform': platform,
                'version': version or "latest",
                'difficulty': difficulty,
                'max_players': max_players,
                'whitelist': whitelist,
                'online_mode': True,  # Default
                'view_distance': 16,  # Default
                'seed': ""  # Default random
            }
            
            # Show confirmation
            await self.manager.show_confirmation(interaction)
            
        except Exception as e:
            logger.error(f"Setup modal error: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {e}", 
                ephemeral=True
            )


class AdvancedSetupModal(ui.Modal, title="⚙️ Advanced Settings"):
    """Optional advanced settings - RAM, view distance, seed"""
    
    max_ram = ui.TextInput(
        label="Max RAM (GB)",
        placeholder="4",
        default="4",
        max_length=2,
        required=False
    )
    
    min_ram = ui.TextInput(
        label="Min RAM (GB)",
        placeholder="2",
        default="2",
        max_length=2,
        required=False
    )
    
    view_distance = ui.TextInput(
        label="View Distance (chunks)",
        placeholder="16",
        default="16",
        max_length=2,
        required=False
    )
    
    seed = ui.TextInput(
        label="World Seed (leave empty for random)",
        placeholder="",
        required=False,
        max_length=50
    )
    
    cracked_mode = ui.TextInput(
        label="Cracked/Offline Mode?",
        placeholder="yes or no (default: no)",
        default="no",
        max_length=3,
        required=False
    )
    
    def __init__(self, setup_manager):
        super().__init__()
        self.manager = setup_manager
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate RAM
            max_ram = int(self.max_ram.value or "4")
            min_ram = int(self.min_ram.value or "2")
            
            if not 1 <= min_ram <= max_ram <= 32:
                await interaction.response.send_message(
                    "❌ RAM must be valid: 1 <= min <= max <= 32", 
                    ephemeral=True
                )
                return
            
            # View distance
            view_distance = int(self.view_distance.value or "16")
            if not 3 <= view_distance <= 32:
                await interaction.response.send_message(
                    "❌ View distance must be between 3 and 32", 
                    ephemeral=True
                )
                return
            
            # Seed
            seed = (self.seed.value or "").strip()
            
            # Cracked mode
            cracked_input = (self.cracked_mode.value or "no").lower().strip()
            online_mode = cracked_input not in ["yes", "y", "true", "1", "on"]
            
            # Update config
            self.manager.config['max_ram'] = max_ram
            self.manager.config['min_ram'] = min_ram
            self.manager.config['view_distance'] = view_distance
            self.manager.config['seed'] = seed
            self.manager.config['online_mode'] = online_mode
            
            # Update global config for RAM
            config.JAVA_XMX = f"{max_ram}G"
            config.JAVA_XMS = f"{min_ram}G"
            
            await interaction.response.send_message(
                f"✅ Advanced settings updated!\\n"
                f"RAM: {min_ram}G - {max_ram}G\\n"
                f"View Distance: {view_distance}\\n"
                f"Seed: {seed or 'Random'}\\n"
                f"Mode: {'Cracked (Offline)' if not online_mode else 'Online'}",
                ephemeral=True
            )
            
            # Refresh confirmation embed
            await self.manager.update_confirmation()
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid number format", 
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Advanced settings error: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {e}", 
                ephemeral=True
            )


class ConfirmationView(ui.View):
    """View with Confirm and Advanced Settings buttons"""
    
    def __init__(self, setup_manager):
        super().__init__(timeout=600)  # 10 minute timeout
        self.manager = setup_manager
    
    @ui.button(label="✅ Confirm & Install", style=discord.ButtonStyle.green, row=0)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        """User confirmed - start installation"""
        await self.manager.start_installation(interaction)
        self.stop()
    
    @ui.button(label="⚙️ Advanced Settings", style=discord.ButtonStyle.primary, row=0)
    async def advanced_button(self, interaction: discord.Interaction, button: ui.Button):
        """Show advanced settings modal"""
        modal = AdvancedSetupModal(self.manager)
        await interaction.response.send_modal(modal)
    
    @ui.button(label="🔄 Start Over", style=discord.ButtonStyle.secondary, row=1)
    async def restart_button(self, interaction: discord.Interaction, button: ui.Button):
        """Restart setup from beginning"""
        await self.manager.restart_setup(interaction)
        self.stop()
    
    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel setup"""
        await interaction.response.edit_message(
            content="❌ Setup cancelled.",
            embed=None,
            view=None
        )
        self.stop()


class SetupManager:
    """Manages the new consolidated setup flow"""
    
    def __init__(self, interaction: discord.Interaction, message: discord.Message = None):
        self.interaction = interaction
        self.message = message
        self.config = {}
    
    async def show_confirmation(self, interaction: discord.Interaction):
        """Show beautiful confirmation embed with all settings"""
        
        # Create beautiful embed similar to the image
        embed = discord.Embed(
            title="🎮 Minecraft Server Configuration",
            description="Please review your settings before installation",
            color=0x5865F2  # Discord blurple
        )
        
        # Platform emoji mapping
        platform_emojis = {
            'paper': '📄',
            'vanilla': '🧊',
            'fabric': '🧵'
        }
        
        # Difficulty emoji mapping
        difficulty_emojis = {
            'peaceful': '☮️',
            'easy': '😊',
            'normal': '⚔️',
            'hard': '💀'
        }
        
        # Basic settings section
        basic_info = (
            f"{platform_emojis.get(self.config['platform'], '📦')} **Platform:** {self.config['platform'].title()}\\n"
            f"🏷️ **Version:** {self.config['version'] if self.config['version'] != 'latest' else 'Latest'}\\n"
            f"{difficulty_emojis.get(self.config['difficulty'], '⚔️')} **Difficulty:** {self.config['difficulty'].title()}\\n"
            f"👥 **Max Players:** {self.config['max_players']}\\n"
            f"🔒 **Whitelist:** {'Enabled' if self.config['whitelist'] else 'Disabled'}"
        )
        embed.add_field(name="📋 Basic Settings", value=basic_info, inline=False)
        
        # Advanced settings (if set)
        if 'max_ram' in self.config:
            advanced_info = (
                f"💾 **RAM:** {self.config.get('min_ram', 2)}G - {self.config.get('max_ram', 4)}G\\n"
                f"👁️ **View Distance:** {self.config.get('view_distance', 16)} chunks\\n"
                f"🌱 **Seed:** {self.config.get('seed') or 'Random'}\\n"
                f"🌐 **Mode:** {'Cracked (Offline)' if not self.config.get('online_mode', True) else 'Online'}"
            )
            embed.add_field(name="⚙️ Advanced Settings", value=advanced_info, inline=False)
        
        # What will happen
        embed.add_field(
            name="📦 Installation Process",
            value=(
                "1️⃣ Create Discord channels (command, log, debug)\\n"
                "2️⃣ Create roles (MC Admin, MC Player)\\n"
                "3️⃣ Download Minecraft server\\n"
                "4️⃣ Configure server settings\\n"
                "5️⃣ Accept EULA & prepare world"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="Click 'Confirm & Install' to proceed • Use 'Advanced Settings' for more options",
            icon_url=interaction.client.user.display_avatar.url if interaction.client.user.display_avatar else None
        )
        
        view = ConfirmationView(self)
        
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.errors.InteractionResponded:
            if self.message:
                await self.message.edit(embed=embed, view=view)
            else:
                self.message = await interaction.followup.send(embed=embed, view=view)
    
    async def update_confirmation(self):
        """Update confirmation embed after advanced settings change"""
        if not self.message:
            return
        
        # Recreate the embed with updated config
        embed = discord.Embed(
            title="🎮 Minecraft Server Configuration",
            description="Please review your settings before installation",
            color=0x5865F2
        )
        
        platform_emojis = {'paper': '📄', 'vanilla': '🧊', 'fabric': '🧵'}
        difficulty_emojis = {'peaceful': '☮️', 'easy': '😊', 'normal': '⚔️', 'hard': '💀'}
        
        basic_info = (
            f"{platform_emojis.get(self.config['platform'], '📦')} **Platform:** {self.config['platform'].title()}\\n"
            f"🏷️ **Version:** {self.config['version'] if self.config['version'] != 'latest' else 'Latest'}\\n"
            f"{difficulty_emojis.get(self.config['difficulty'], '⚔️')} **Difficulty:** {self.config['difficulty'].title()}\\n"
            f"👥 **Max Players:** {self.config['max_players']}\\n"
            f"🔒 **Whitelist:** {'Enabled' if self.config['whitelist'] else 'Disabled'}"
        )
        embed.add_field(name="📋 Basic Settings", value=basic_info, inline=False)
        
        if 'max_ram' in self.config:
            advanced_info = (
                f"💾 **RAM:** {self.config.get('min_ram', 2)}G - {self.config.get('max_ram', 4)}G\\n"
                f"👁️ **View Distance:** {self.config.get('view_distance', 16)} chunks\\n"
                f"🌱 **Seed:** {self.config.get('seed') or 'Random'}\\n"
                f"🌐 **Mode:** {'Cracked (Offline)' if not self.config.get('online_mode', True) else 'Online'}"
            )
            embed.add_field(name="⚙️ Advanced Settings", value=advanced_info, inline=False)
        
        embed.add_field(
            name="📦 Installation Process",
            value=(
                "1️⃣ Create Discord channels (command, log, debug)\\n"
                "2️⃣ Create roles (MC Admin, MC Player)\\n"
                "3️⃣ Download Minecraft server\\n"
                "4️⃣ Configure server settings\\n"
                "5️⃣ Accept EULA & prepare world"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="Click 'Confirm & Install' to proceed • Updated with advanced settings ✅"
        )
        
        view = ConfirmationView(self)
        await self.message.edit(embed=embed, view=view)
    
    async def restart_setup(self, interaction: discord.Interaction):
        """Restart setup process from modal"""
        modal = SetupConfigModal(self)
        await interaction.response.send_modal(modal)
    
    async def start_installation(self, interaction: discord.Interaction):
        """User confirmed - begin installation"""
        await interaction.response.defer()
        
        # Update to show installation started
        embed = discord.Embed(
            title="⏳ Installation Starting...",
            description="Setting up your Minecraft server. This may take a few minutes.",
            color=0xFEE75C  # Yellow
        )
        await self.message.edit(embed=embed, view=None)
        
        # STEP 1: Discord Structure Setup
        from src.setup_helper import SetupHelper
        
        try:
            embed.description = "**Step 1/5:** Creating Discord channels and roles..."
            await self.message.edit(embed=embed)
            
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
            await self.message.edit(embed=embed)
            return
        
        # STEP 2: Download server
        try:
            embed.description = f"**Step 2/5:** Downloading {self.config['platform'].title()} server..."
            await self.message.edit(embed=embed)
            
            # Get version if "latest"
            if self.config['version'] == 'latest':
                self.config['version'] = await mc_installer.get_latest_version(self.config['platform'])
            
            async def progress_callback(msg):
                embed.description = f"**Step 2/5:** {msg}"
                try:
                    await self.message.edit(embed=embed)
                except:
                    pass
            
            success, message = await mc_installer.download_server(
                self.config['platform'],
                self.config['version'],
                progress_callback
            )
            
            if not success:
                raise Exception(message)
            
        except Exception as e:
            logger.error(f"Server download failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ Download failed: {e}"
            await self.message.edit(embed=embed)
            return
        
        # STEP 3: Accept EULA
        try:
            embed.description = "**Step 3/5:** Accepting Minecraft EULA..."
            await self.message.edit(embed=embed)
            
            await mc_installer.accept_eula()
            
        except Exception as e:
            logger.error(f"EULA acceptance failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ EULA failed: {e}"
            await self.message.edit(embed=embed)
            return
        
        # STEP 4: Configure server
        try:
            embed.description = "**Step 4/5:** Configuring server settings..."
            await self.message.edit(embed=embed)
            
            await mc_installer.configure_server_properties(self.config)
            
        except Exception as e:
            logger.error(f"Server configuration failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"❌ Configuration failed: {e}"
            await self.message.edit(embed=embed)
            return
        
        # STEP 5: Complete!
        embed.description = "**Step 5/5:** Finalizing setup..."
        await self.message.edit(embed=embed)
        
        # Success embed
        await self.show_success()
    
    async def show_success(self):
        """Show beautiful success message"""
        command_channel = self.interaction.client.get_channel(config.COMMAND_CHANNEL_ID)
        
        embed = discord.Embed(
            title="✅ Installation Complete!",
            description="Your Minecraft server is ready to launch!",
            color=0x57F287  # Green
        )
        
        embed.add_field(
            name="📋 Server Details",
            value=(
                f"**Platform:** {self.config['platform'].title()}\\n"
                f"**Version:** {self.config['version']}\\n"
                f"**Difficulty:** {self.config['difficulty'].title()}\\n"
                f"**Max Players:** {self.config['max_players']}\\n"
                f"**Whitelist:** {'Enabled' if self.config['whitelist'] else 'Disabled'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚀 Quick Start",
            value=(
                f"1. Go to {command_channel.mention if command_channel else '#command'}\\n"
                f"2. Run `/start` to launch the server\\n"
                f"3. Wait for world generation (first start takes time)\\n"
                f"4. Use `/status` to check when it's online"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🌐 Multiplayer Setup",
            value=(
                "⚠️ For others to connect, you need:\\n"
                "• Port forwarding (25565)\\n"
                "• OR use [playit.gg](https://playit.gg) for easy access"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use /help to see all available commands")
        
        await self.message.edit(embed=embed, view=None)
    
    async def _save_config_to_file(self, updates: dict):
        """Save configuration updates to config.json file"""
        import json
        try:
            with open('config.json', 'r') as f:
                config_data = json.load(f)
            
            if 'command_channel_id' in updates:
                config_data['command_channel_id'] = updates['command_channel_id']
            if 'log_channel_id' in updates:
                config_data['log_channel_id'] = updates['log_channel_id']
            if 'debug_channel_id' in updates:
                config_data['debug_channel_id'] = updates['debug_channel_id']
            if 'roles' in updates:
                config_data['roles'] = updates['roles']
            
            with open('config.json', 'w') as f:
                json.dump(config_data, f, indent='\\t')
                f.write('\\n')
            
            logger.info("config.json updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update config.json: {e}")
            raise
