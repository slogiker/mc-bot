import discord
from discord import app_commands
from discord.ext import commands
import logging
import aiohttp
import os
import aiofiles
import asyncio
from src.config import config
from src.utils import has_role, send_debug, get_server_mod_folder

logger = logging.getLogger('mc_bot')




class InstalledModsView(discord.ui.View):
    def __init__(self, mod_files, folder_path):
        super().__init__(timeout=600)
        self.folder_path = folder_path
        self.mod_files = mod_files[:25] # Discord max=25
        
        options = []
        for i, mf in enumerate(self.mod_files):
            label = mf[:100] # Discord label max = 100 chars
            options.append(discord.SelectOption(label=label, value=str(i)))
            
        self.select = discord.ui.Select(placeholder="Select an installed mod to delete...", min_values=1, max_values=1, options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        idx = int(self.select.values[0])
        filename = self.mod_files[idx]
        filepath = os.path.join(self.folder_path, filename)
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                await interaction.response.send_message(f"🗑️ Successfully deleted `{filename}`.\n*Please restart the server to apply changes.*", ephemeral=True)
                await send_debug(interaction.client, f"Deleted mod {filename} via Mod Manager")
                
                # Try to clean up the UI
                self.remove_item(self.select)
                await interaction.message.edit(view=self)
            else:
                await interaction.response.send_message(f"❌ File `{filename}` is no longer present on the server.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to delete mod {filename}: {e}")
            await interaction.response.send_message(f"❌ Could not delete `{filename}`: {e}", ephemeral=True)


class ModsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _modrinth_search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                params = {"query": query, "limit": limit, "index": "relevance"}
                async with session.get("https://api.modrinth.com/v2/search", params=params) as resp:
                    if resp.status == 200:
                        return (await resp.json()).get("hits", [])
        except Exception:
            pass
        return []

    @app_commands.command(name="mod_search", description="Search and install up to 5 mods/plugins from Modrinth")
    @app_commands.describe(
        mod1="First mod/plugin to install",
        mod2="Second mod/plugin to install (optional)",
        mod3="Third mod/plugin to install (optional)",
        mod4="Fourth mod/plugin to install (optional)",
        mod5="Fifth mod/plugin to install (optional)"
    )
    @has_role("mods")
    async def mod_search(
        self, 
        interaction: discord.Interaction, 
        mod1: str, 
        mod2: str = None, 
        mod3: str = None, 
        mod4: str = None, 
        mod5: str = None
    ):
        await interaction.response.defer()
        msg = await interaction.followup.send("⏳ Initializing mod installation...")

        # Collect all selected slugs and remove duplicates
        slugs = [s for s in [mod1, mod2, mod3, mod4, mod5] if s]
        slugs = list(dict.fromkeys(slugs))

        # Get server version
        mc_version = getattr(config, 'INSTALLED_VERSION', None)
        if not mc_version or mc_version == "Unknown":
            from src.utils import parse_server_version
            mc_version = await parse_server_version()
        if not mc_version or mc_version == "Unknown":
            mc_version = "1.20.1"

        # Auto-detect loader
        dest_folder = await get_server_mod_folder()
        if dest_folder is None:
            await msg.edit(content="❌ Mods and plugins are not supported on Vanilla servers.")
            return
        loader = "fabric" if dest_folder == "mods" else "paper"

        installed_files = []
        failed_mods = []

        async with aiohttp.ClientSession() as session:
            for i, slug in enumerate(slugs):
                await msg.edit(content=f"📥 [{i+1}/{len(slugs)}] Locating latest compatible version for `{slug}`...")

                api_url = f"https://api.modrinth.com/v2/project/{slug}/version"
                params = {
                    "loaders": f'["{loader}"]',
                    "game_versions": f'["{mc_version}"]'
                }

                try:
                    async with session.get(api_url, params=params) as resp:
                        if resp.status != 200:
                            failed_mods.append(f"`{slug}` (API error)")
                            continue

                        versions = await resp.json()
                        if not versions:
                            failed_mods.append(f"`{slug}` (no version for {mc_version} / {loader})")
                            continue

                        latest_file = versions[0]['files'][0]
                        download_url = latest_file['url']
                        filename = latest_file['filename']

                        dest_path = os.path.join(config.SERVER_DIR, dest_folder, filename)

                        await msg.edit(content=f"📥 [{i+1}/{len(slugs)}] Downloading `{filename}`...")

                        async with session.get(download_url) as file_resp:
                            if file_resp.status == 200:
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                async with aiofiles.open(dest_path, mode='wb') as f:
                                    await f.write(await file_resp.read())
                                installed_files.append(filename)
                            else:
                                failed_mods.append(f"`{slug}` (download error)")
                except Exception as e:
                    logger.error(f"Failed to download {slug}: {e}")
                    failed_mods.append(f"`{slug}` ({str(e)})")

        # Build final status embed
        embed = discord.Embed(title="📦 Mod Installation Results", color=discord.Color.green())
        if installed_files:
            embed.add_field(name="✅ Successfully Installed", value="\n".join([f"• `{f}`" for f in installed_files]), inline=False)
        if failed_mods:
            embed.add_field(name="❌ Failed to Install", value="\n".join([f"• {m}" for m in failed_mods]), inline=False)

        await msg.edit(content=None, embed=embed)

        if installed_files:
            await send_debug(interaction.client, f"📥 **Mods installed!**\n" + "\n".join([f"• `{f}`" for f in installed_files]) + "\nServer will restart in 10 seconds. Take a quick water break! 💧")

            # Automatic restart
            if self.bot.server.is_running():
                await asyncio.sleep(10)
                success, restart_msg = await self.bot.server.restart()
                if success:
                    await send_debug(interaction.client, "🚀 **Server Restarted!** Mod changes are now active.")
                else:
                    await send_debug(interaction.client, f"⚠️ **Automatic restart failed:** {restart_msg}. Please restart manually.")

    @mod_search.autocomplete("mod1")
    @mod_search.autocomplete("mod2")
    @mod_search.autocomplete("mod3")
    @mod_search.autocomplete("mod4")
    @mod_search.autocomplete("mod5")
    async def mod_search_autocomplete(self, interaction: discord.Interaction, current: str):
        if len(current) < 2:
            return []
        hits = await self._modrinth_search(current, limit=8)
        type_icon = {"plugin": "🔧", "mod": "🧩", "modpack": "📦"}
        return [
            app_commands.Choice(
                name=f"{type_icon.get(h.get('project_type',''), '📦')} {h.get('title','?')} ({h.get('slug','?')})"[:100],
                value=h.get("slug", "")
            )
            for h in hits
        ]



    @app_commands.command(name="update", description="Holistic server upgrade: downloads the latest JAR for the target version and updates all mods")
    @app_commands.describe(version="The target Minecraft version (e.g., 1.21.1)")
    @has_role("mods")
    async def update_everything(self, interaction: discord.Interaction, version: str):
        await interaction.response.defer(ephemeral=False)
        msg_obj = await interaction.followup.send(f"🔄 **Starting Universal Server Upgrader** for target version: `{version}`...")
        
        async def updater_callback(status_text):
            try:
                await msg_obj.edit(content=f"🔄 **Upgrading to {version}...**\n{status_text}")
            except Exception:
                pass
                
        # 1. Server Installer Phase
        await updater_callback("🛠️ Checking server platform...")
        from src.mc_installer import mc_installer
        
        # We need to guess the platform based on folder structure
        dest_folder = await get_server_mod_folder()
        platform = "vanilla"
        if dest_folder == "plugins":
            platform = "paper"
        elif getattr(config, 'INSTALLED_VERSION', '').lower().find('fabric') != -1 or dest_folder == "mods":
            platform = "fabric"
            
        await updater_callback(f"🛠️ Detected platform `{platform}`. Fetching core server JAR...")
        
        success, install_msg = await mc_installer.download_server(platform, version, updater_callback)
        if not success:
             await msg_obj.edit(content=f"❌ **Server Core Upgrade Failed:** {install_msg}")
             return
             
        # Cache the new version
        config.update_dynamic_config({"installed_version": f"{platform}-{version}"})
        
        # 2. Mod Updater Phase
        if platform != "vanilla":
            await updater_callback("✅ Server Core updated. Initializing Mod/Plugin Upgrader...")
            from src.mod_updater import ModUpdater
            updater = ModUpdater(callback=updater_callback)
            await updater.update_all(game_version=version)
        else:
            await updater_callback("✅ Server Core updated. Skipping Mod/Plugin Upgrader (Vanilla platform).")
        
        await msg_obj.reply(f"✅ **Update Complete!** The server core has been updated to `{version}`.\nYou can now `/start` the server.")


async def setup(bot):
    await bot.add_cog(ModsCog(bot))
