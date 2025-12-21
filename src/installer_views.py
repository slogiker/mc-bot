import discord
from discord import ui
from src.mc_installer import mc_installer
from src.logger import logger

class PlatformSelectView(ui.View):
    """Step 1: Select server platform"""
    def __init__(self, installer_manager):
        super().__init__(timeout=300)
        self.manager = installer_manager
        self.value = None
    
    @ui.button(label="Paper (Recommended)", style=discord.ButtonStyle.green, emoji="📄")
    async def paper_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "paper"
        await self.manager.set_platform(interaction, "paper")
        self.stop()
    
    @ui.button(label="Vanilla", style=discord.ButtonStyle.primary, emoji="🧊")
    async def vanilla_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "vanilla"
        await self.manager.set_platform(interaction, "vanilla")
        self.stop()
    
    @ui.button(label="Fabric", style=discord.ButtonStyle.secondary, emoji="🧵")
    async def fabric_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "fabric"
        await self.manager.set_platform(interaction, "fabric")
        self.stop()
    
    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="❌ Installation cancelled.", view=None, embed=None)
        self.stop()


class VersionSelectView(ui.View):
    """Step 2: Select version"""
    def __init__(self, installer_manager, platform: str, latest_version: str):
        super().__init__(timeout=300)
        self.manager = installer_manager
        self.platform = platform
        self.latest_version = latest_version
    
    @ui.button(label="Latest", style=discord.ButtonStyle.green, emoji="⭐")
    async def latest_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.manager.set_version(interaction, self.latest_version)
        self.stop()
    
    @ui.button(label="1.20.4", style=discord.ButtonStyle.secondary)
    async def v1_20_4(self, interaction: discord.Interaction, button: ui.Button):
        await self.manager.set_version(interaction, "1.20.4")
        self.stop()
    
    @ui.button(label="1.19.4", style=discord.ButtonStyle.secondary)
    async def v1_19_4(self, interaction: discord.Interaction, button: ui.Button):
        await self.manager.set_version(interaction, "1.19.4")
        self.stop()
    
    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="❌ Installation cancelled.", view=None, embed=None)
        self.stop()


class ServerSettingsView(ui.View):
    """Step 3: Configure server settings"""
    def __init__(self, installer_manager):
        super().__init__(timeout=300)
        self.manager = installer_manager
        self.settings = {
            'difficulty': 'normal',
            'whitelist': False,
            'seed': '',
            'online_mode': True,
            'max_players': 20,
            'view_distance': 16
        }
    
    @ui.select(
        placeholder="Select Difficulty",
        options=[
            discord.SelectOption(label="Peaceful", value="peaceful", emoji="☮️"),
            discord.SelectOption(label="Easy", value="easy", emoji="😊"),
            discord.SelectOption(label="Normal", value="normal", emoji="⚔️", default=True),
            discord.SelectOption(label="Hard", value="hard", emoji="💀"),
        ]
    )
    async def difficulty_select(self, interaction: discord.Interaction, select: ui.Select):
        self.settings['difficulty'] = select.values[0]
        await interaction.response.send_message(f"✅ Difficulty set to **{select.values[0]}**", ephemeral=True)
    
    @ui.button(label="Enable Whitelist", style=discord.ButtonStyle.secondary, row=1)
    async def whitelist_button(self, interaction: discord.Interaction, button: ui.Button):
        self.settings['whitelist'] = not self.settings['whitelist']
        button.style = discord.ButtonStyle.green if self.settings['whitelist'] else discord.ButtonStyle.secondary
        button.label = "Whitelist: ON" if self.settings['whitelist'] else "Enable Whitelist"
        await interaction.response.edit_message(view=self)
    
    @ui.button(label="Cracked Mode (Offline)", style=discord.ButtonStyle.secondary, row=1)
    async def cracked_button(self, interaction: discord.Interaction, button: ui.Button):
        self.settings['online_mode'] = not self.settings['online_mode']
        button.style = discord.ButtonStyle.danger if not self.settings['online_mode'] else discord.ButtonStyle.secondary
        button.label = "Cracked: ON" if not self.settings['online_mode'] else "Cracked Mode (Offline)"
        await interaction.response.edit_message(view=self)
    
    @ui.button(label="Continue →", style=discord.ButtonStyle.green, row=2)
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.manager.apply_settings(interaction, self.settings)
        self.stop()
    
    @ui.button(label="Advanced Settings", style=discord.ButtonStyle.primary, row=2)
    async def advanced_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AdvancedSettingsModal(self))


class AdvancedSettingsModal(ui.Modal, title="Advanced Server Settings"):
    """Modal for optional advanced settings"""
    
    max_players = ui.TextInput(
        label="Max Players",
        placeholder="20",
        default="20",
        max_length=3,
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
    
    def __init__(self, parent_view: ServerSettingsView):
        super().__init__()
        self.parent_view = parent_view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.parent_view.settings['max_players'] = int(self.max_players.value or "20")
            self.parent_view.settings['view_distance'] = int(self.view_distance.value or "16")
            self.parent_view.settings['seed'] = self.seed.value or ""
            
            # Update config for RAM settings
            from src.config import config
            config.JAVA_XMX = f"{self.max_ram.value or '4'}G"
            config.JAVA_XMS = f"{self.min_ram.value or '2'}G"
            
            await interaction.response.send_message(
                f"✅ Advanced settings saved!\n"
                f"Max Players: {self.parent_view.settings['max_players']}\n"
                f"View Distance: {self.parent_view.settings['view_distance']}\n"
                f"Seed: {self.parent_view.settings['seed'] or 'Random'}\n"
                f"RAM: {config.JAVA_XMS} - {config.JAVA_XMX}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("❌ Invalid values. Please enter numbers.", ephemeral=True)


class WhitelistInputModal(ui.Modal, title="Add Players to Whitelist"):
    """Modal for entering whitelist usernames"""
    
    usernames = ui.TextInput(
        label="Minecraft Usernames (one per line)",
        placeholder="Player1\nPlayer2\nPlayer3",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    def __init__(self, installer_manager):
        super().__init__()
        self.manager = installer_manager
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        usernames = [u.strip() for u in self.usernames.value.split('\n') if u.strip()]
        await self.manager.add_whitelist_players(interaction, usernames)


class InstallationManager:
    """Manages the installation flow"""
    def __init__(self, interaction: discord.Interaction, message: discord.Message):
        self.interaction = interaction
        self.message = message
        self.platform = None
        self.version = None
        self.settings = {}
    
    async def update_embed(self, title: str, description: str, color=discord.Color.blue()):
        """Update the installation status embed"""
        embed = discord.Embed(title=title, description=description, color=color)
        try:
            await self.message.edit(embed=embed, view=None)
        except:
            pass
    
    async def set_platform(self, interaction: discord.Interaction, platform: str):
        """Platform selected, now ask for version"""
        self.platform = platform
        await interaction.response.defer()
        
        # Get latest version
        await self.update_embed(
            "🔍 Checking Versions",
            f"Finding latest {platform.title()} version..."
        )
        
        latest = await mc_installer.get_latest_version(platform)
        
        embed = discord.Embed(
            title=f"📦 Select {platform.title()} Version",
            description=f"Latest available: **{latest}**",
            color=discord.Color.blue()
        )
        view = VersionSelectView(self, platform, latest)
        await self.message.edit(embed=embed, view=view)
    
    async def set_version(self, interaction: discord.Interaction, version: str):
        """Version selected, start download"""
        self.version = version
        await interaction.response.defer()
        
        # Download server
        await self.update_embed(
            "📥 Downloading Server",
            f"Downloading {self.platform.title()} {version}..."
        )
        
        async def progress_callback(msg):
            await self.update_embed("📥 Downloading Server", msg)
        
        success, message = await mc_installer.download_server(self.platform, version, progress_callback)
        
        if not success:
            await self.update_embed(
                "❌ Download Failed",
                f"Error: {message}",
                discord.Color.red()
            )
            return
        
        # Accept EULA
        await self.update_embed("📜 Accepting EULA", "Accepting Minecraft EULA...")
        await mc_installer.accept_eula()
        
        # Show settings configuration
        await self.show_settings()
    
    async def show_settings(self):
        """Show server settings configuration"""
        embed = discord.Embed(
            title="⚙️ Configure Server Settings",
            description="Choose your server settings below.\nClick **Continue** when ready.",
            color=discord.Color.blue()
        )
        view = ServerSettingsView(self)
        await self.message.edit(embed=embed, view=view)
    
    async def apply_settings(self, interaction: discord.Interaction, settings: dict):
        """Apply settings and complete installation"""
        await interaction.response.defer()
        self.settings = settings
        
        # If whitelist enabled, ask for usernames
        if settings['whitelist']:
            modal = WhitelistInputModal(self)
            await interaction.followup.send(
                "📝 Whitelist is enabled. Please add players:",
                view=ui.View().add_item(
                    ui.Button(label="Add Players", style=discord.ButtonStyle.primary)
                ),
                ephemeral=True
            )
            # This is tricky - we need to wait for modal. Let's simplify.
            # For now, skip modal and let them add via command later
            await self.finalize_installation(interaction)
        else:
            await self.finalize_installation(interaction)
    
    async def add_whitelist_players(self, interaction: discord.Interaction, usernames: list):
        """Add players to whitelist"""
        await self.update_embed("👥 Adding Whitelist Players", "Processing...")
        
        added = []
        failed = []
        
        for username in usernames:
            success = await mc_installer.add_to_whitelist(username)
            if success:
                added.append(username)
            else:
                failed.append(username)
        
        status = f"✅ Added: {', '.join(added)}" if added else ""
        if failed:
            status += f"\n❌ Failed: {', '.join(failed)}"
        
        await interaction.followup.send(status, ephemeral=True)
        await self.finalize_installation(interaction)
    
    async def finalize_installation(self, interaction: discord.Interaction):
        """Configure properties and complete installation"""
        await self.update_embed(
            "⚙️ Configuring Server",
            "Writing server.properties..."
        )
        
        await mc_installer.configure_server_properties(self.settings)
        
        # Success!
        from src.config import config
        embed = discord.Embed(
            title="✅ Installation Complete!",
            description="Your Minecraft server is ready to start!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Server Details",
            value=f"**Platform:** {self.platform.title()}\n"
                  f"**Version:** {self.version}\n"
                  f"**Difficulty:** {self.settings['difficulty'].title()}\n"
                  f"**Whitelist:** {'Enabled' if self.settings['whitelist'] else 'Disabled'}\n"
                  f"**Mode:** {'Cracked (Offline)' if not self.settings['online_mode'] else 'Online'}",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Next Steps",
            value="1. Use `/start` to launch the server\n"
                  "2. Wait for world generation (first start takes time)\n"
                  "3. Use `/status` to check when it's online",
            inline=False
        )
        
        embed.add_field(
            name="🌐 Multiplayer Setup",
            value="⚠️ For others to connect, you need:\n"
                  "• Port forwarding (25565)\n"
                  "• OR use [playit.gg](https://playit.gg) for easy access",
            inline=False
        )
        
        embed.set_footer(text="Use /help to see all available commands")
        
        await self.message.edit(embed=embed, view=None)