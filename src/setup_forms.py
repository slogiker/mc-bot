"""
Modern Form-Based Setup System
Similar to discordforms.app - clean, intuitive form interface
"""

import discord
from discord import ui
from src.mc_installer import mc_installer
from src.logger import logger
from src.config import config
from src.version_fetcher import version_fetcher


class SetupFormView(ui.View):
    """Initial setup view with select menus for platform, version, and difficulty"""
    
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
        self.platform = None
        self.version = None
        self.difficulty = None
        self.versions_loading = False
    
    @ui.select(
        placeholder="Select Platform...",
        options=[
            discord.SelectOption(label="Paper", value="paper", description="Recommended for plugins", emoji="📄"),
            discord.SelectOption(label="Vanilla", value="vanilla", description="Official Minecraft server", emoji="🎮"),
            discord.SelectOption(label="Fabric", value="fabric", description="Mod loader", emoji="🧵"),
        ],
        row=0
    )
    async def platform_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle platform selection"""
        self.platform = select.values[0]
        
        # Update version select with loading state
        self.version_select.disabled = True
        self.version_select.placeholder = "Loading versions..."
        self.version_select.options = [
            discord.SelectOption(label="Loading...", value="loading", description="Fetching versions", default=True)
        ]
        
        await interaction.response.edit_message(view=self)
        
        # Fetch versions asynchronously
        try:
            versions = await version_fetcher.get_versions(self.platform, limit=5)
            
            # Build version options
            options = [
                discord.SelectOption(label="Latest", value="latest", description="Most recent version", default=True, emoji="⭐")
            ]
            
            for version in versions:
                options.append(
                    discord.SelectOption(
                        label=version,
                        value=version,
                        description=f"{self.platform.title()} {version}"
                    )
                )
            
            # Add "More..." option
            options.append(
                discord.SelectOption(
                    label="More...",
                    value="__more__",
                    description="Show all available versions",
                    emoji="📋"
                )
            )
            
            self.version_select.options = options
            self.version_select.disabled = False
            self.version_select.placeholder = "Select Version..."
            
            await interaction.edit_original_response(view=self)
            
        except Exception as e:
            logger.error(f"Failed to load versions: {e}")
            self.version_select.options = [
                discord.SelectOption(label="Latest", value="latest", description="Use latest version", default=True)
            ]
            self.version_select.disabled = False
            self.version_select.placeholder = "Select Version (using latest)"
            await interaction.edit_original_response(view=self)
    
    @ui.select(
        placeholder="Select Version...",
        options=[
            discord.SelectOption(label="Select platform first", value="__disabled__", default=True, disabled=True)
        ],
        disabled=True,
        row=1
    )
    async def version_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle version selection"""
        selected = select.values[0]
        
        if selected == "__more__":
            # Show modal with all versions
            await interaction.response.send_modal(AllVersionsModal(self.platform, self))
            return
        
        if selected == "__disabled__" or selected == "loading":
            await interaction.response.defer()
            return
        
        self.version = selected
        
        # Update the select to show selected version
        for option in select.options:
            option.default = (option.value == selected)
        
        await interaction.response.edit_message(view=self)
    
    @ui.select(
        placeholder="Select Difficulty...",
        options=[
            discord.SelectOption(label="Peaceful", value="peaceful", description="No mobs, no hunger", emoji="🕊️"),
            discord.SelectOption(label="Easy", value="easy", description="Fewer mobs, less damage", emoji="😊"),
            discord.SelectOption(label="Normal", value="normal", description="Standard gameplay", emoji="⚔️", default=True),
            discord.SelectOption(label="Hard", value="hard", description="More mobs, more damage", emoji="💀"),
        ],
        row=2
    )
    async def difficulty_select(self, interaction: discord.Interaction, select: ui.Select):
        """Handle difficulty selection"""
        self.difficulty = select.values[0]
        await interaction.response.defer()
    
    @ui.button(label="Continue to Basic Settings", style=discord.ButtonStyle.primary, row=3, emoji="➡️")
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        """Continue to basic settings modal"""
        # Validate selections
        if not self.platform:
            await interaction.response.send_message("❌ Please select a platform first.", ephemeral=True)
            return
        
        if not self.version:
            await interaction.response.send_message("❌ Please select a version.", ephemeral=True)
            return
        
        if not self.difficulty:
            await interaction.response.send_message("❌ Please select a difficulty.", ephemeral=True)
            return
        
        # Open basic settings modal
        modal = BasicSettingsModal(self.platform, self.version, self.difficulty)
        await interaction.response.send_modal(modal)
    
    @ui.button(label="Advanced Settings", style=discord.ButtonStyle.secondary, row=3, emoji="⚙️")
    async def advanced_button(self, interaction: discord.Interaction, button: ui.Button):
        """Open advanced settings (can be accessed before or after basic)"""
        # Store current selections if any
        modal = AdvancedSettingsModal(
            platform=self.platform or "paper",
            version=self.version or "latest",
            difficulty=self.difficulty or "normal"
        )
        await interaction.response.send_modal(modal)


class AllVersionsModal(ui.Modal, title="All Available Versions"):
    """Modal to show all versions with autocomplete"""
    
    version_input = ui.TextInput(
        label="Version",
        placeholder="Type version (e.g., 1.20.4) or select from list",
        required=True,
        max_length=20
    )
    
    def __init__(self, platform: str, parent_view: SetupFormView):
        super().__init__()
        self.platform = platform
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        version = self.version_input.value.strip()
        
        # Validate version exists
        try:
            all_versions = await version_fetcher.get_all_versions(self.platform)
            if version.lower() == "latest":
                version = "latest"
            elif version not in all_versions:
                # Try to find close match
                close_matches = [v for v in all_versions if version in v]
                if close_matches:
                    version = close_matches[0]
                    await interaction.response.send_message(
                        f"✅ Using version: {version}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ Version '{version}' not found. Using latest instead.",
                        ephemeral=True
                    )
                    version = "latest"
        except Exception as e:
            logger.error(f"Error validating version: {e}")
            version = "latest"
        
        self.parent_view.version = version
        
        # Update the select menu to show selected version
        try:
            # Update options to show selected version
            updated_options = []
            for option in self.parent_view.version_select.options:
                if option.value == version:
                    option.default = True
                else:
                    option.default = False
                updated_options.append(option)
            
            self.parent_view.version_select.options = updated_options
            
            # Edit the original message to show updated view
            await interaction.response.send_message(
                f"✅ Version set to: {version}. You can continue with the setup.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error updating version select: {e}")
            await interaction.response.send_message(
                f"✅ Version set to: {version}",
                ephemeral=True
            )


class BasicSettingsModal(ui.Modal, title="Basic Server Settings"):
    """Modal for basic server settings"""
    
    max_players = ui.TextInput(
        label="Max Players",
        placeholder="20",
        default="20",
        max_length=3,
        required=True
    )
    
    max_ram = ui.TextInput(
        label="Max RAM (GB)",
        placeholder="4",
        default="4",
        max_length=2,
        required=True
    )
    
    def __init__(self, platform: str, version: str, difficulty: str):
        super().__init__()
        self.platform = platform
        self.version = version
        self.difficulty = difficulty
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate max players
            try:
                max_players = int(self.max_players.value)
                if not 1 <= max_players <= 100:
                    raise ValueError()
            except ValueError:
                await interaction.response.send_message(
                    "❌ Max players must be a number between 1 and 100.",
                    ephemeral=True
                )
                return
            
            # Validate max RAM
            try:
                user_max_ram = int(self.max_ram.value)
                if not 1 <= user_max_ram <= 32:
                    raise ValueError()
            except ValueError:
                await interaction.response.send_message(
                    "❌ Max RAM must be a number between 1 and 32 GB.",
                    ephemeral=True
                )
                return
            
            # Calculate min RAM (at least 50% of user's max, minimum 1GB)
            min_ram = max(1, int(user_max_ram * 0.5))
            # Calculate max RAM as min + 2GB (per user requirement)
            max_ram = min_ram + 2
            
            # If user entered a value that results in max < their input, adjust
            if user_max_ram > max_ram:
                # User wants more RAM, so use their value as max and recalculate min
                max_ram = user_max_ram
                min_ram = max(1, int(max_ram * 0.5))
                # Ensure max is still at least min + 2GB
                if max_ram < min_ram + 2:
                    max_ram = min_ram + 2
            
            # Build config
            setup_config = {
                'platform': self.platform,
                'version': self.version,
                'difficulty': self.difficulty,
                'max_players': max_players,
                'min_ram': min_ram,
                'max_ram': max_ram,
                'whitelist': False,
                'online_mode': True,
                'view_distance': 16,
                'seed': "",
            }
            
            # Update global config for RAM
            config.JAVA_XMX = f"{max_ram}G"
            config.JAVA_XMS = f"{min_ram}G"
            
            # Start installation
            await self.start_installation(interaction, setup_config)
            
        except Exception as e:
            logger.error(f"Basic settings modal error: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {e}",
                ephemeral=True
            )
    
    async def start_installation(self, interaction: discord.Interaction, setup_config: dict):
        """Start installation and show progress"""
        from src.setup_helper import SetupHelper
        
        # Create initial progress embed
        embed = discord.Embed(
            title="⏳ Installing Minecraft Server",
            description="**Step 1/5:** Preparing installation...",
            color=0xFEE75C
        )
        embed.add_field(
            name="📋 Configuration",
            value=(
                f"**Platform:** {setup_config['platform'].title()}\n"
                f"**Version:** {setup_config['version']}\n"
                f"**Difficulty:** {setup_config['difficulty'].title()}\n"
                f"**Max Players:** {setup_config['max_players']}\n"
                f"**RAM:** {setup_config['min_ram']}GB - {setup_config['max_ram']}GB"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # STEP 1: Discord Structure Setup
        try:
            embed.description = "**Step 1/5:** Creating Discord channels and roles..."
            await message.edit(embed=embed)
            
            setup_helper = SetupHelper(interaction.client)
            updates = await setup_helper.ensure_setup(interaction.guild)
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
                setup_config['version'] = await version_fetcher.get_latest_version(setup_config['platform'])
            
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
        
        command_channel = interaction.client.get_channel(config.COMMAND_CHANNEL_ID)
        
        embed = discord.Embed(
            title="✅ Installation Complete!",
            description="Your Minecraft server is ready to launch!",
            color=0x57F287
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
            
            with open('bot_config.json', 'w') as f:
                json.dump(config_data, f, indent='\t')
                f.write('\n')
            
            logger.info("config.json updated successfully")
        except Exception as e:
            logger.error(f"Failed to update config.json: {e}")
            raise


class AdvancedSettingsModal(ui.Modal, title="Advanced Server Settings"):
    """Modal for advanced server settings"""
    
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
    
    min_ram = ui.TextInput(
        label="Min RAM (GB)",
        placeholder="2",
        default="2",
        max_length=2,
        required=False
    )
    
    max_ram = ui.TextInput(
        label="Max RAM (GB)",
        placeholder="4",
        default="4",
        max_length=2,
        required=False
    )
    
    def __init__(self, platform: str = "paper", version: str = "latest", difficulty: str = "normal"):
        super().__init__()
        self.platform = platform
        self.version = version
        self.difficulty = difficulty
    
    async def on_submit(self, interaction: discord.Interaction):
        """Save advanced settings (can be used to update existing server)"""
        try:
            # Parse settings
            view_distance = int(self.view_distance.value or "16")
            seed = self.seed.value.strip() if self.seed.value else ""
            min_ram = int(self.min_ram.value or "2")
            max_ram = int(self.max_ram.value or "4")
            
            # Validate
            if not 2 <= view_distance <= 32:
                await interaction.response.send_message(
                    "❌ View distance must be between 2 and 32 chunks.",
                    ephemeral=True
                )
                return
            
            if not 1 <= min_ram <= 32 or not 1 <= max_ram <= 32:
                await interaction.response.send_message(
                    "❌ RAM must be between 1 and 32 GB.",
                    ephemeral=True
                )
                return
            
            if max_ram < min_ram:
                await interaction.response.send_message(
                    "❌ Max RAM must be greater than or equal to Min RAM.",
                    ephemeral=True
                )
                return
            
            # Update config
            config.JAVA_XMX = f"{max_ram}G"
            config.JAVA_XMS = f"{min_ram}G"
            
            # If server.properties exists, update it
            import os
            import aiofiles
            props_path = os.path.join(config.SERVER_DIR, "server.properties")
            
            if os.path.exists(props_path):
                # Read and update server.properties
                async with aiofiles.open(props_path, 'r') as f:
                    content = await f.read()
                
                lines = content.split('\n')
                updated_lines = []
                for line in lines:
                    if line.startswith('view-distance='):
                        updated_lines.append(f'view-distance={view_distance}\n')
                    elif line.startswith('level-seed='):
                        updated_lines.append(f'level-seed={seed}\n')
                    elif not line.strip().startswith('#') and '=' in line:
                        updated_lines.append(line + '\n')
                    else:
                        updated_lines.append(line + '\n')
                
                async with aiofiles.open(props_path, 'w') as f:
                    await f.write(''.join(updated_lines))
                
                await interaction.response.send_message(
                    "✅ Advanced settings updated! Restart the server for changes to take effect.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "✅ Advanced settings saved! These will be applied when you run `/setup`.",
                    ephemeral=True
                )
                
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid input. Please enter numbers only for numeric fields.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Advanced settings error: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error: {e}",
                ephemeral=True
            )
