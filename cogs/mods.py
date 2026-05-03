import discord
from discord import app_commands
from discord.ext import commands
import logging
import aiohttp
import os
import aiofiles
from src.config import config
from src.utils import has_role, send_debug

logger = logging.getLogger('mc_bot')

class ModrinthSelect(discord.ui.Select):
    def __init__(self, search_results):
        options = []
        for mod in search_results:
            # Title might be long
            label = mod.get('title', 'Unknown')[:100]
            desc = mod.get('description', '')[:100]
            val = mod.get('slug', '')
            options.append(discord.SelectOption(label=label, description=desc, value=val))
            
        super().__init__(placeholder="Select a mod/plugin to install...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        slug = self.values[0]
        # In a full implementation, we would now query the API for the specific slug + version + loader
        # and download it async. For now, we defer to the view's handle_selection
        await self.view.handle_selection(interaction, slug)

class ModrinthSearchView(discord.ui.View):
    def __init__(self, search_results, bot):
        super().__init__(timeout=600)
        self.bot = bot
        self.add_item(ModrinthSelect(search_results))

    async def handle_selection(self, interaction: discord.Interaction, slug: str):
        await interaction.response.defer()
        msg = await interaction.followup.send(f"⏳ Locating latest compatible version for `{slug}`...", wait=True)
        
        # 1. Get current server version - check config first, then parse from log
        mc_version = getattr(config, 'INSTALLED_VERSION', None)
        if not mc_version or mc_version == "Unknown":
            from src.utils import parse_server_version
            mc_version = await parse_server_version()
        if not mc_version or mc_version == "Unknown":
            mc_version = "1.20.1" # Last resort fallback
        
        # 2. Auto-detect loader from server directory structure
        loader = "fabric"
        if os.path.exists(os.path.join(config.SERVER_DIR, "plugins")):
             loader = "paper"
             
        api_url = f"https://api.modrinth.com/v2/project/{slug}/version"
        params = {
            "loaders": f'["{loader}"]',
            "game_versions": f'["{mc_version}"]'
        }
        
        try:
             async with aiohttp.ClientSession() as session:
                 async with session.get(api_url, params=params) as resp:
                     if resp.status != 200:
                         await msg.edit(content=f"❌ Failed to find a `{loader}` version of `{slug}` compatible with Minecraft `{mc_version}`.")
                         return
                         
                     versions = await resp.json()
                     if not versions:
                         await msg.edit(content=f"❌ No compatible versions found for `{slug}` on {mc_version}.")
                         return
                         
                     # Get latest file
                     latest_file = versions[0]['files'][0]
                     download_url = latest_file['url']
                     filename = latest_file['filename']
                     
                     # 3. Download it
                     dest_folder = "mods" if loader == "fabric" else "plugins"
                     dest_path = os.path.join(config.SERVER_DIR, dest_folder, filename)
                     
                     await msg.edit(content=f"📥 Downloading `{filename}`...")
                     
                     async with session.get(download_url) as file_resp:
                         if file_resp.status == 200:
                             os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                             async with aiofiles.open(dest_path, mode='wb') as f:
                                 await f.write(await file_resp.read())
                             await msg.edit(content=f"✅ Successfully installed `{filename}` into `{dest_folder}/`.\n*Please restart the server to apply changes.*")
                             await send_debug(interaction.client, f"Installed {slug} ({filename}) via Modrinth UI")
                         else:
                             await msg.edit(content=f"❌ Failed to download `{filename}`.")
        except Exception as e:
            logger.error(f"Modrinth download failed: {e}")
            await msg.edit(content=f"❌ An error occurred during download: {str(e)}")


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

    @app_commands.command(name="mod_search", description="Search and install mods/plugins from Modrinth")
    @app_commands.describe(query="Name or slug of the mod/plugin — autocomplete searches as you type")
    @has_role("mods")
    async def mod_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        hits = await self._modrinth_search(query)

        if not hits:
            await interaction.followup.send(f"❌ No results found for `{query}`.")
            return

        type_icon = {"plugin": "🔧", "mod": "🧩", "modpack": "📦"}
        lines = []
        for h in hits[:10]:
            icon = type_icon.get(h.get("project_type", ""), "📦")
            name = h.get("title", "?")
            slug = h.get("slug", "?")
            summary = h.get("description", "")[:72]
            downloads = h.get("downloads", 0)
            dl = f"{downloads:,}"
            lines.append(f"{icon} **{name}** — slug: `{slug}` · {dl} downloads\n  *{summary}*")

        view = ModrinthSearchView(hits, self.bot)
        embed = discord.Embed(
            title=f"Modrinth Search: {query}",
            description="\n\n".join(lines) + "\n\nSelect from the dropdown to install directly.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, view=view)

    @mod_search.autocomplete("query")
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
        platform = "vanilla"
        if os.path.exists(os.path.join(config.SERVER_DIR, "plugins")):
            platform = "paper"
        elif getattr(config, 'INSTALLED_VERSION', '').lower().find('fabric') != -1 or os.path.exists(os.path.join(config.SERVER_DIR, "mods")):
            platform = "fabric"
            
        await updater_callback(f"🛠️ Detected platform `{platform}`. Fetching core server JAR...")
        
        success, install_msg = await mc_installer.download_server(platform, version, updater_callback)
        if not success:
             await msg_obj.edit(content=f"❌ **Server Core Upgrade Failed:** {install_msg}")
             return
             
        # Cache the new version
        config.update_dynamic_config({"installed_version": f"{platform}-{version}"})
        
        # 2. Mod Updater Phase
        await updater_callback("✅ Server Core updated. Initializing Mod/Plugin Upgrader...")
        from src.mod_updater import ModUpdater
        updater = ModUpdater(callback=updater_callback)
        await updater.update_all(game_version=version)
        
        await msg_obj.reply(f"✅ **Update Complete!** The server core and all compatible mods/plugins have been updated to `{version}`.\nYou can now `/start` the server.")


async def setup(bot):
    await bot.add_cog(ModsCog(bot))
