"""
Modern Interactive Setup Form
Multi-step form using Discord Select menus and Buttons for beautiful UX
"""

import discord
import asyncio
import subprocess
from discord import ui
from typing import Optional, Dict, Any
from src.mc_installer import mc_installer
from src.logger import logger
from src.config import config
import aiohttp
from src.setup_helper import SetupHelper
from src.mod_updater import ModUpdater
from src.utils import rcon_cmd
from src.server_info_manager import ServerInfoManager

GLOBAL_VERSIONS = []

async def fetch_versions():
    global GLOBAL_VERSIONS
    if GLOBAL_VERSIONS: return GLOBAL_VERSIONS
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.modrinth.com/v2/tag/game_version") as resp:
                data = await resp.json()
                # Get the first 24 release versions
                GLOBAL_VERSIONS = [v['version'] for v in data if v['version_type'] == 'release'][:24]
                return GLOBAL_VERSIONS
    except Exception as e:
        logger.error(f"Failed to fetch Modrinth versions: {e}")
        GLOBAL_VERSIONS = ["26.1.2", "26.1.1", "26.1", "25.4.1", "25.3"] # Fallback
        return GLOBAL_VERSIONS

class SetupState:
    """Manages the state of the setup process"""
    def __init__(self):
        self.platform: str = "paper"
        self.version: str = "latest"
        self.difficulty: str = "normal"
        self.max_players: int = 20
        self.ram: int = 4
        # Advanced settings
        self.whitelist: bool = False
        self.online_mode: bool = True
        self.view_distance: int = 16
        self.seed: str = ""
        self.plugins: str = ""
        self.current_step: int = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to config dictionary"""
        return {
            'platform': self.platform,
            'version': self.version,
            'difficulty': self.difficulty,
            'max_players': self.max_players,
            'whitelist': self.whitelist,
            'online_mode': self.online_mode,
            'view_distance': self.view_distance,
            'seed': self.seed,
            'max_ram': self.ram,
            'min_ram': max(1, self.ram // 2),
            'plugins': self.plugins
        }


class PlatformSelect(ui.Select):
    """Dropdown for selecting server platform"""
    def __init__(self, current_platform: str = "paper"):
        options = [
            discord.SelectOption(
                label="Paper",
                value="paper",
                description="Recommended - Best performance & plugin support",
                default=(current_platform == "paper")
            ),
            discord.SelectOption(
                label="Vanilla",
                value="vanilla",
                description="Official Minecraft server",
                default=(current_platform == "vanilla")
            ),
            discord.SelectOption(
                label="Fabric",
                value="fabric",
                description="Lightweight modding platform",
                default=(current_platform == "fabric")
            )
        ]
        super().__init__(
            placeholder=f"Currently: {current_platform.title()}",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: SetupView = self.view
        view.state.platform = self.values[0]
        await interaction.response.defer()
        await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)


class VersionSelect(ui.Select):
    """Dropdown for selecting Minecraft version"""
    def __init__(self, platform: str = "paper", current_value: str = "latest"):
        versions = GLOBAL_VERSIONS if GLOBAL_VERSIONS else ["26.1.2", "26.1.1"]
        
        options = []
        for i, version in enumerate(versions[:24]):  # Discord limit is 25
            label = f"{version} (latest)" if i == 0 else version
            options.append(
                discord.SelectOption(
                    label=label,
                    value=version,
                    default=(current_value == version or (i == 0 and current_value == "latest"))
                )
            )
        
        # Add custom option
        options.append(
            discord.SelectOption(
                label="Custom Version",
                value="custom",
                description="Enter specific version"
            )
        )
        
        super().__init__(
            placeholder=f"Currently: {current_value}",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: SetupView = self.view
        if self.values[0] == "custom":
            # Show modal for custom version input
            modal = CustomVersionModal(view.state.version)
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value:
                view.state.version = modal.value
            await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)
        else:
            view.state.version = self.values[0]
            await interaction.response.defer()
            await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)


class CustomVersionModal(ui.Modal, title="Custom Version"):
    """Modal for custom version input"""
    def __init__(self, current_value: str):
        super().__init__()
        self.value: Optional[str] = None
        
        self.version_input = ui.TextInput(
            label="Minecraft Version",
            placeholder="e.g., 1.20.4 or latest",
            default=current_value,
            max_length=20,
            required=True
        )
        self.add_item(self.version_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.version_input.value.strip()
        await interaction.response.defer()


class DifficultySelect(ui.Select):
    """Dropdown for selecting difficulty"""
    def __init__(self, current_value: str = "normal"):
        options = [
            discord.SelectOption(
                label="Peaceful",
                value="peaceful",
                description="No hostile mobs",
                default=(current_value == "peaceful")
            ),
            discord.SelectOption(
                label="Easy",
                value="easy",
                description="Reduced mob damage",
                default=(current_value == "easy")
            ),
            discord.SelectOption(
                label="Normal",
                value="normal",
                description="Standard gameplay",
                default=(current_value == "normal")
            ),
            discord.SelectOption(
                label="Hard",
                value="hard",
                description="Increased challenge",
                default=(current_value == "hard")
            )
        ]
        super().__init__(
            placeholder=f"Currently: {current_value.title()}",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: SetupView = self.view
        view.state.difficulty = self.values[0]
        await interaction.response.defer()
        await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)


class SeedModal(ui.Modal, title="World Seed"):
    """Modal for custom world seed input"""
    def __init__(self, current_value: str):
        super().__init__()
        self.value: Optional[str] = None
        
        self.seed_input = ui.TextInput(
            label="World Seed",
            placeholder="Leave empty for random seed",
            default=current_value,
            max_length=50,
            required=False
        )
        self.add_item(self.seed_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.value = self.seed_input.value.strip()
        await interaction.response.defer()


class SeedButton(ui.Button):
    """Button to set world seed"""
    def __init__(self):
        super().__init__(label="Set Seed", style=discord.ButtonStyle.primary)
    
    async def callback(self, interaction: discord.Interaction):
        view: SetupView = self.view
        modal = SeedModal(view.state.seed)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value is not None:
            view.state.seed = modal.value
        await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)


class MaxPlayersSelect(ui.Select):
    """Dropdown for selecting max players"""
    def __init__(self, current_value: int = 20):
        options = [
            discord.SelectOption(label="5 Players", value="5", default=(current_value == 5)),
            discord.SelectOption(label="10 Players", value="10", default=(current_value == 10)),
            discord.SelectOption(label="20 Players", value="20", default=(current_value == 20)),
            discord.SelectOption(label="50 Players", value="50", default=(current_value == 50)),
            discord.SelectOption(label="100 Players", value="100", default=(current_value == 100)),
            discord.SelectOption(label="Custom Amount", value="custom", description="Enter custom value")
        ]
        known = {5: "5", 10: "10", 20: "20", 50: "50", 100: "100"}
        label = known.get(current_value, str(current_value))
        super().__init__(
            placeholder=f"Currently: {label} Players",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: SetupView = self.view
        if self.values[0] == "custom":
            modal = CustomNumberModal(
                title="Custom Max Players",
                label="Max Players (1-100)",
                current_value=str(view.state.max_players),
                min_val=1,
                max_val=100
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value:
                view.state.max_players = modal.value
            await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)
        else:
            view.state.max_players = int(self.values[0])
            await interaction.response.defer()
            await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)


class RAMSelect(ui.Select):
    """Dropdown for selecting RAM"""
    def __init__(self, current_value: int = 4):
        options = [
            discord.SelectOption(label="1 GB", value="1", description="Minimal", default=(current_value == 1)),
            discord.SelectOption(label="2 GB", value="2", description="Small server", default=(current_value == 2)),
            discord.SelectOption(label="4 GB", value="4", description="Recommended", default=(current_value == 4)),
            discord.SelectOption(label="8 GB", value="8", description="Large server", default=(current_value == 8)),
            discord.SelectOption(label="16 GB", value="16", description="Very large", default=(current_value == 16)),
            discord.SelectOption(label="32 GB", value="32", description="Maximum", default=(current_value == 32)),
            discord.SelectOption(label="Custom Amount", value="custom", description="Enter custom value")
        ]
        known = {1, 2, 4, 8, 16, 32}
        label = f"{current_value} GB" if current_value in known else f"{current_value} GB (custom)"
        super().__init__(
            placeholder=f"Currently: {label}",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: SetupView = self.view
        if self.values[0] == "custom":
            modal = CustomNumberModal(
                title="Custom RAM Amount",
                label="RAM in GB (1-32)",
                current_value=str(view.state.ram),
                min_val=1,
                max_val=32
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value:
                view.state.ram = modal.value
            await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)
        else:
            view.state.ram = int(self.values[0])
            await interaction.response.defer()
            await view.message.edit(embed=view._get_step_content(view.state.current_step)[0], view=view)


class CustomNumberModal(ui.Modal):
    """Modal for custom number input"""
    def __init__(self, title: str, label: str, current_value: str, min_val: int, max_val: int):
        super().__init__(title=title)
        self.min_val = min_val
        self.max_val = max_val
        self.value: Optional[int] = None
        
        self.number_input = ui.TextInput(
            label=label,
            placeholder=f"Enter number between {min_val} and {max_val}",
            default=current_value,
            max_length=3,
            required=True
        )
        self.add_item(self.number_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Strip non-numeric characters
            clean_value = ''.join(filter(str.isdigit, self.number_input.value))
            if not clean_value:
                raise ValueError("No number provided")
            
            value = int(clean_value)
            if not self.min_val <= value <= self.max_val:
                raise ValueError(f"Must be between {self.min_val} and {self.max_val}")
            
            self.value = value
            await interaction.response.defer()
        except ValueError as e:
            await interaction.response.send_message(
                f"Invalid input: {e}\nPlease enter a number between {self.min_val} and {self.max_val}",
                ephemeral=True
            )

class SetupView(ui.View):
    """Main view controller for multi-step setup"""
    
    STEPS = [
        "Platform",
        "Version", 
        "Difficulty",
        "Seed",
        "Max Players",
        "Advanced Settings",
        "Confirmation"
    ]
    
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=600)  # 10 minute timeout
        self.interaction = interaction
        self.state = SetupState()
        self.message: Optional[discord.Message] = None
        
    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(
                content="Setup timed out — run /setup again.", embed=None, view=None
            )
        except Exception:
            pass

    async def start(self):
        """Start the setup process"""
        embed, view_items = self._get_step_content(0)
        self.clear_items()
        for item in view_items:
            self.add_item(item)

        await self.interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await self.interaction.original_response()
    
    def _get_step_content(self, step: int) -> tuple[discord.Embed, list]:
        """Get embed and view items for current step"""
        self.state.current_step = step
        
        # Progress indicator
        progress = f"Step {step + 1}/{len(self.STEPS)}"
        
        if step == 0:  # Platform
            embed = discord.Embed(
                title="Minecraft Server Setup",
                description=f"**{progress}** - Choose your server platform",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Current Selection",
                value=f"**{self.state.platform.title()}**",
                inline=False
            )
            return embed, [PlatformSelect(self.state.platform), self._next_button()]
            
        elif step == 1:  # Version
            embed = discord.Embed(
                title="Minecraft Server Setup",
                description=f"**{progress}** - Choose Minecraft version",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Current Selection",
                value=f"**{self.state.version}**",
                inline=False
            )
            embed.set_footer(text="Tip: The first option will always use the newest version")
            return embed, [VersionSelect(self.state.platform, self.state.version), self._back_button(), self._next_button()]

            
        elif step == 2:  # Difficulty
            embed = discord.Embed(
                title="Minecraft Server Setup",
                description=f"**{progress}** - Choose difficulty level",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Current Selection",
                value=f"**{self.state.difficulty.title()}**",
                inline=False
            )
            return embed, [DifficultySelect(self.state.difficulty), self._back_button(), self._next_button()]
            
        elif step == 3:  # Seed
            embed = discord.Embed(
                title="Minecraft Server Setup",
                description=f"**{progress}** - Set world seed (optional)",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Current Selection",
                value=f"**{self.state.seed or 'Random'}**",
                inline=False
            )
            seed_btn = SeedButton()
            return embed, [seed_btn, self._back_button(), self._next_button()]
            
        elif step == 4:  # Max Players
            embed = discord.Embed(
                title="Minecraft Server Setup",
                description=f"**{progress}** - Set maximum players",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Current Selection",
                value=f"**{self.state.max_players} players**",
                inline=False
            )
            return embed, [MaxPlayersSelect(self.state.max_players), self._back_button(), self._next_button()]
            
        elif step == 5:  # Advanced Settings (now with RAM)
            embed = discord.Embed(
                title="Minecraft Server Setup",
                description=f"**{progress}** - Advanced Settings",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Current Settings",
                value=(
                    f"**RAM:** {self.state.ram} GB\n"
                    f"**Whitelist:** {'Enabled' if self.state.whitelist else 'Disabled'}\n"
                    f"**Online Mode:** {'Enabled' if self.state.online_mode else 'Disabled'}\n"
                    f"**View Distance:** {self.state.view_distance} chunks"
                ),
                inline=False
            )
            return embed, [self._back_button(), self._configure_advanced_button(), self._next_button()]
            
        else:  # Confirmation (step 6)
            embed = discord.Embed(
                title="Ready to Install",
                description="Review your configuration and click Install to begin",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Configuration Summary",
                value=(
                    f"**Platform:** {self.state.platform.title()}\n"
                    f"**Version:** {self.state.version}{' (Latest available will be used)' if self.state.version == 'latest' else ''}\n"
                    f"**Difficulty:** {self.state.difficulty.title()}\n"
                    f"**Seed:** {self.state.seed or 'Random'}\n"
                    f"**Max Players:** {self.state.max_players}\n"
                    f"**RAM:** {self.state.ram} GB\n"
                    f"**Whitelist:** {'Enabled' if self.state.whitelist else 'Disabled'}\n"
                    f"**Online Mode:** {'Enabled' if self.state.online_mode else 'Disabled'}"
                ),
                inline=False
            )
            return embed, [self._back_button(), self._install_button()]
    
    def _next_button(self) -> ui.Button:
        """Create Next button"""
        button = ui.Button(label="Next", style=discord.ButtonStyle.primary)
        async def callback(interaction: discord.Interaction):
            await self._navigate(interaction, self.state.current_step + 1)
        button.callback = callback
        return button
    
    def _back_button(self) -> ui.Button:
        """Create Back button"""
        button = ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        async def callback(interaction: discord.Interaction):
            await self._navigate(interaction, self.state.current_step - 1)
        button.callback = callback
        return button
    
    def _skip_button(self) -> ui.Button:
        """Create Skip button"""
        button = ui.Button(label="Skip", style=discord.ButtonStyle.secondary)
        async def callback(interaction: discord.Interaction):
            await self._navigate(interaction, self.state.current_step + 1)
        button.callback = callback
        return button
    
    def _configure_advanced_button(self) -> ui.Button:
        """Create Configure Advanced button"""
        button = ui.Button(label="Configure", style=discord.ButtonStyle.primary)
        async def callback(interaction: discord.Interaction):
            modal = AdvancedSettingsModal(self.state)
            await interaction.response.send_modal(modal)
            await modal.wait()
            # Refresh current view
            await self.message.edit(embed=self._get_step_content(self.state.current_step)[0], view=self)
        button.callback = callback
        return button
    
    def _install_button(self) -> ui.Button:
        """Create Install button"""
        button = ui.Button(label="Install Now", style=discord.ButtonStyle.success)
        async def callback(interaction: discord.Interaction):
            await self._start_installation(interaction)
        button.callback = callback
        return button
    
    async def _navigate(self, interaction: discord.Interaction, new_step: int):
        """Navigate to a different step"""
        if new_step < 0 or new_step >= len(self.STEPS):
            return
        
        embed, view_items = self._get_step_content(new_step)
        self.clear_items()
        for item in view_items:
            self.add_item(item)
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _start_installation(self, interaction: discord.Interaction):
        """Start the installation process in background"""
        
        # Create initial progress embed
        embed = discord.Embed(
            title="Installing Minecraft Server",
            description="**Step 1/5:** Preparing installation...",
            color=0xFEE75C  # Yellow
        )
        embed.add_field(
            name="Configuration",
            value=(
                f"**Platform:** {self.state.platform.title()}\n"
                f"**Version:** {self.state.version}\n"
                f"**Difficulty:** {self.state.difficulty.title()}\n"
                f"**Max Players:** {self.state.max_players}\n"
                f"**RAM:** {self.state.ram}G"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        message = await interaction.original_response()
        
        # Run installation in background
        setup_config = self.state.to_dict()
        config.JAVA_XMX = f"{self.state.ram}G"
        config.JAVA_XMS = f"{max(1, self.state.ram // 2)}G"
        
        try:
            from src.utils import send_debug
            await send_debug(interaction.client, f"🚀 **Starting fresh installation of {setup_config['platform']} {setup_config['version']}**")
            
            embed.description = "**Step 1/5:** Creating Discord channels and roles..."
            await message.edit(embed=embed)
            
            setup_helper = SetupHelper(interaction.client)
            updates = await setup_helper.ensure_setup(interaction.guild)
            
            # Update config
            config.update_dynamic_config(updates)
            await self._save_config_to_file(updates)
            
            logger.info(f"Discord setup completed by {interaction.user.name}")
            await send_debug(interaction.client, "✅ Step 1: Discord channels and roles created.")
            
            # STEP 2: Download server
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
            await send_debug(interaction.client, f"✅ Step 2: Downloaded {setup_config['platform']} {setup_config['version']}.")
            
            # STEP 2.5: Generate Files
            embed.description = "**Step 2.5/5:** Launching server to generate files..."
            await message.edit(embed=embed)
            await send_debug(interaction.client, "⏳ Step 2.5: Running jar to generate eula.txt...")
            
            proc = await asyncio.create_subprocess_exec(
                "java", "-jar", "server.jar", "nogui",
                cwd=config.SERVER_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Wait for it to exit due to EULA missing
            try:
                await asyncio.wait_for(proc.wait(), timeout=60.0)
                await send_debug(interaction.client, "✅ EULA generation exited naturally.")
            except asyncio.TimeoutError:
                proc.kill()
                await send_debug(interaction.client, "⚠️ EULA generation killed after 60s timeout.")
            
            # STEP 3: Accept EULA
            embed.description = "**Step 3/5:** Accepting Minecraft EULA..."
            await message.edit(embed=embed)
            
            await mc_installer.accept_eula()
            await send_debug(interaction.client, "✅ Step 3: Accepted Minecraft EULA.")
            
            # STEP 4: Configure server
            embed.description = "**Step 4/5:** Configuring server settings..."
            await message.edit(embed=embed)
            
            await mc_installer.configure_server_properties(setup_config)
            await send_debug(interaction.client, "✅ Step 4: Configured server.properties.")
            
            # Save resolved version and platform to config
            version_update = {
                'installed_version': setup_config['version'],
                'installed_platform': setup_config['platform'],
            }
            config.update_dynamic_config(version_update)
            await self._save_config_to_file(version_update)

            # STEP 5: Start server
            embed.description = "**Step 5/5:** Starting server for first time..."
            await message.edit(embed=embed)
            await send_debug(interaction.client, "⏳ Step 5: Starting Tmux server session...")
            
            # Start the server using the bot's server instance
            start_success, start_msg = await interaction.client.server.start()
            
            if not start_success:
                logger.warning(f"Server failed to start after installation: {start_msg}")
                await send_debug(interaction.client, f"❌ Failed to start server: {start_msg}")
            
            # Wait for server to actually be ready (via logs)
            server_ready = False
            if start_success:
                embed.description = "**Step 5/5:** Server started, waiting for it to be fully ready..."
                await message.edit(embed=embed)
                
                await send_debug(interaction.client, "⏳ Server booting up. Waiting for 'Done' signal in console logs (can take a few minutes)...")
                from src.log_dispatcher import log_dispatcher
                if await log_dispatcher.wait_for_pattern('Done (', timeout=300):
                    server_ready = True
                    await send_debug(interaction.client, "✅ Server is fully booted and ready!")
                else:
                    logger.warning("Server started but 'Done' log not detected after 5m timeout")
                    await send_debug(interaction.client, "⚠️ Timed out waiting for server boot log. It might still be starting.")
            
            # Success embed
            command_channel = interaction.client.get_channel(config.COMMAND_CHANNEL_ID)
            
            status_text = "Online" if server_ready else ("Starting..." if start_success else "Ready to start")
            
            embed = discord.Embed(
                title="Installation Complete!",
                description=f"Your Minecraft server is ready! Server status: **{status_text}**",
                color=0x57F287  # Green
            )
            
            embed.add_field(
                name="Quick Start",
                value=(
                    f"1. Server is {status_text.lower()}\n"
                    f"2. Use `/info` to see server details\n"
                    f"3. Use `/control` for the control panel\n"
                    f"4. Check {command_channel.mention if command_channel else '#command'} for commands"
                ),
                inline=False
            )
            
            embed.set_footer(text="Use /help to see all available commands")
            await message.edit(embed=embed)
            
            # Broadcast readiness to the command channel
            if server_ready and command_channel:
                try:
                    info_cog = interaction.client.get_cog("Info")
                    if info_cog:
                        info_embed = await info_cog.build_info_embed(interaction.guild)
                        await command_channel.send(content="🎉 **Your Minecraft server is ready!**", embed=info_embed)
                except Exception as e:
                    logger.error(f"Failed to broadcast server readiness: {e}")
            
            # Trigger control panel update immediately so it shows correct status
            try:
                control_cog = interaction.client.get_cog("ControlPanelCog")
                if control_cog:
                    await control_cog.update_panel()
            except Exception as e:
                logger.error(f"Failed to update control panel: {e}")
            
            # Initialize server info channel
            try:
                from src.server_info_manager import ServerInfoManager
                await ServerInfoManager(interaction.client).update_info(interaction.guild)
            except Exception as e:
                logger.error(f"Failed to init server info channel: {e}")
            
        except Exception as e:
            logger.error(f"Installation failed: {e}", exc_info=True)
            embed.color = discord.Color.red()
            embed.description = f"Installation failed: {str(e)}"
            await message.edit(embed=embed)
    
    async def _save_config_to_file(self, updates: dict):
        """Save configuration updates to bot_config.json file"""
        try:
            def update():
                with config.update_bot_config() as data:
                    data.update(updates)
            await asyncio.to_thread(update)
            logger.info("data/bot_config.json updated successfully")
        except Exception as e:
            logger.error(f"Failed to update data/bot_config.json: {e}")


class AdvancedSettingsModal(ui.Modal, title="⚙️ Advanced Settings"):
    """Modal for advanced server settings"""
    
    def __init__(self, state: SetupState):
        super().__init__()
        self.state = state
        
        self.ram = ui.TextInput(
            label="RAM Allocation in GB",
            placeholder="4",
            default=str(state.ram),
            max_length=2,
            required=False
        )
        self.add_item(self.ram)
        
        self.view_distance = ui.TextInput(
            label="View Distance (chunks)",
            placeholder="16",
            default=str(state.view_distance),
            max_length=2,
            required=False
        )
        self.add_item(self.view_distance)
        
        self.whitelist = ui.TextInput(
            label="Enable Whitelist? (yes/no)",
            placeholder="no",
            default="yes" if state.whitelist else "no",
            max_length=3,
            required=False
        )
        self.add_item(self.whitelist)
        
        self.online_mode = ui.TextInput(
            label="Enable Online Mode? (yes/no)",
            placeholder="yes",
            default="yes" if state.online_mode else "no",
            max_length=3,
            required=False
        )
        self.add_item(self.online_mode)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse RAM
            ram_clean = ''.join(filter(str.isdigit, self.ram.value or "4"))
            self.state.ram = int(ram_clean) if ram_clean else 4
            
            # Parse view distance
            vd_clean = ''.join(filter(str.isdigit, self.view_distance.value or "16"))
            self.state.view_distance = int(vd_clean) if vd_clean else 16
            
            # Parse whitelist
            self.state.whitelist = self.whitelist.value.lower().strip() in ["yes", "y", "true", "1"]
            
            # Parse online mode
            self.state.online_mode = self.online_mode.value.lower().strip() in ["yes", "y", "true", "1"]
            
            await interaction.response.defer()
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)
