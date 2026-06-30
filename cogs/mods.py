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

class ModrinthSelect(discord.ui.Select):
    def __init__(self, search_results):
        options = []
        for mod in search_results:
            label = mod.get('title', 'Unknown')[:100]
            desc = mod.get('description', '')[:100]
            val = mod.get('slug', '')
            options.append(discord.SelectOption(label=label, description=desc, value=val))
            
        super().__init__(placeholder="Select a mod/plugin to add to queue...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        slug = self.values[0]
        selected_mod = None
        for mod in self.view.current_hits:
            if mod.get('slug') == slug:
                selected_mod = mod
                break
        
        if selected_mod:
            title = selected_mod.get('title', 'Unknown')
            if not any(item['slug'] == slug for item in self.view.cog.queue):
                self.view.cog.queue.append({"title": title, "slug": slug})
                await interaction.response.defer()
                await self.view.update_message(interaction)
            else:
                await interaction.response.send_message(f"ℹ️ `{title}` is already in the queue.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Error: Selected mod not found in search results.", ephemeral=True)


class ModrinthSearchModal(discord.ui.Modal, title="Search and Add Mod"):
    query_input = discord.ui.TextInput(
        label="Search Query",
        placeholder="Enter mod name or slug (e.g. sodium)...",
        required=True,
        max_length=100
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = self.query_input.value
        
        hits = await self.view.cog._modrinth_search(query)
        if not hits:
            await interaction.followup.send(f"❌ No results found for `{query}`.", ephemeral=True)
            return
            
        self.view.current_hits = hits
        self.view.current_query = query
        self.view.update_dropdown(hits)
        await self.view.update_message(interaction)


class ModrinthSearchView(discord.ui.View):
    def __init__(self, search_results, bot, cog, initial_query):
        super().__init__(timeout=600)
        self.bot = bot
        self.cog = cog
        self.current_hits = search_results
        self.current_query = initial_query
        
        # Add the dropdown
        self.add_item(ModrinthSelect(search_results))

    def update_dropdown(self, hits):
        for item in self.children:
            if isinstance(item, ModrinthSelect):
                options = []
                for mod in hits:
                    label = mod.get('title', 'Unknown')[:100]
                    desc = mod.get('description', '')[:100]
                    val = mod.get('slug', '')
                    options.append(discord.SelectOption(label=label, description=desc, value=val))
                item.options = options
                break

    async def update_message(self, interaction: discord.Interaction):
        type_icon = {"plugin": "🔧", "mod": "🧩", "modpack": "📦"}
        lines = []
        for h in self.current_hits[:10]:
            icon = type_icon.get(h.get("project_type", ""), "📦")
            name = h.get("title", "?")
            slug = h.get("slug", "?")
            summary = h.get("description", "")[:72]
            downloads = h.get("downloads", 0)
            dl = f"{downloads:,}"
            lines.append(f"{icon} **{name}** — slug: `{slug}` · {dl} downloads\n  *{summary}*")
            
        queue_lines = []
        if self.cog.queue:
            queue_lines.append("\n🛒 **Pending Mod Queue:**")
            for item in self.cog.queue:
                queue_lines.append(f"• 🧩 **{item['title']}** (`{item['slug']}`)")
        else:
            queue_lines.append("\n🛒 **Pending Mod Queue:** *(Empty)*")
            
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label.startswith("📥 Download"):
                if self.cog.queue:
                    child.label = f"📥 Download & Install ({len(self.cog.queue)})"
                else:
                    child.label = "📥 Download & Install"
                break
                
        embed = discord.Embed(
            title=f"Modrinth Search: {self.current_query}",
            description="\n\n".join(lines) + "\n" + "\n".join(queue_lines) + "\n\nSelect from the dropdown to add to the queue. Click 'Download & Install' when ready.",
            color=discord.Color.green()
        )
        
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="➕ Add Another", style=discord.ButtonStyle.secondary, row=1)
    async def add_another(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ModrinthSearchModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Clear Queue", style=discord.ButtonStyle.danger, row=1)
    async def clear_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.queue = []
        await interaction.response.defer()
        await self.update_message(interaction)

    @discord.ui.button(label="📥 Download & Install", style=discord.ButtonStyle.success, row=1)
    async def download_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.queue:
            await interaction.response.send_message("❌ The queue is empty. Add some mods first!", ephemeral=True)
            return
            
        await interaction.response.defer()
        await interaction.message.edit(content="⏳ Starting downloads...", embed=None, view=None)
        
        mc_version = getattr(config, 'INSTALLED_VERSION', None)
        if not mc_version or mc_version == "Unknown":
            from src.utils import parse_server_version
            mc_version = await parse_server_version()
        if not mc_version or mc_version == "Unknown":
            mc_version = "1.20.1"
            
        dest_folder = await get_server_mod_folder()
        if dest_folder is None:
            await interaction.message.edit(content="❌ Mods and plugins are not supported on Vanilla servers.")
            return
        loader = "fabric" if dest_folder == "mods" else "paper"
        
        installed_files = []
        failed_mods = []
        
        async with aiohttp.ClientSession() as session:
            for i, item in enumerate(self.cog.queue):
                slug = item['slug']
                title = item['title']
                
                await interaction.message.edit(content=f"📥 [{i+1}/{len(self.cog.queue)}] Locating latest compatible version for `{title}`...")
                
                api_url = f"https://api.modrinth.com/v2/project/{slug}/version"
                params = {
                    "loaders": f'["{loader}"]',
                    "game_versions": f'["{mc_version}"]'
                }
                
                try:
                    async with session.get(api_url, params=params) as resp:
                        if resp.status != 200:
                            failed_mods.append(f"`{title}` (API error)")
                            continue
                            
                        versions = await resp.json()
                        if not versions:
                            failed_mods.append(f"`{title}` (no version for {mc_version} / {loader})")
                            continue
                            
                        latest_file = versions[0]['files'][0]
                        download_url = latest_file['url']
                        filename = latest_file['filename']
                        
                        dest_path = os.path.join(config.SERVER_DIR, dest_folder, filename)
                        
                        await interaction.message.edit(content=f"📥 [{i+1}/{len(self.cog.queue)}] Downloading `{filename}`...")
                        
                        async with session.get(download_url) as file_resp:
                            if file_resp.status == 200:
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                async with aiofiles.open(dest_path, mode='wb') as f:
                                    await f.write(await file_resp.read())
                                installed_files.append(filename)
                            else:
                                failed_mods.append(f"`{title}` (download error)")
                except Exception as e:
                    logger.error(f"Failed to download {slug}: {e}")
                    failed_mods.append(f"`{title}` ({str(e)})")
                    
        # Update final status
        status_lines = []
        if installed_files:
            status_lines.append("✅ **Successfully installed:**")
            status_lines.extend([f"• `{f}`" for f in installed_files])
        if failed_mods:
            status_lines.append("\n❌ **Failed to install:**")
            status_lines.extend([f"• {m}" for m in failed_mods])
            
        status_text = "\n".join(status_lines)
        await interaction.message.edit(content=f"📦 **Mod Installation Complete!**\n\n{status_text}")
        
        # Clear queue after installation
        self.cog.queue = []
        
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
            else:
                await interaction.followup.send("💡 Server is currently offline. Start it to apply changes.", ephemeral=True)


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
        self.queue = []

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

        # Check if the query matches a slug exactly (usually when selected via autocomplete)
        exact_match = None
        for h in hits:
            if h.get("slug") == query:
                exact_match = h
                break
        
        if exact_match:
            # Auto-add to the queue
            if not any(item['slug'] == exact_match['slug'] for item in self.queue):
                self.queue.append({"title": exact_match['title'], "slug": exact_match['slug']})

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

        # Build queue display
        queue_lines = []
        if self.queue:
            queue_lines.append("\n🛒 **Pending Mod Queue:**")
            for item in self.queue:
                queue_lines.append(f"• 🧩 **{item['title']}** (`{item['slug']}`)")
        else:
            queue_lines.append("\n🛒 **Pending Mod Queue:** *(Empty)*")

        view = ModrinthSearchView(hits, self.bot, self, query)
        
        # Set the download button label to show the count of queued mods
        for child in view.children:
            if isinstance(child, discord.ui.Button) and child.label.startswith("📥 Download"):
                if self.queue:
                    child.label = f"📥 Download & Install ({len(self.queue)})"
                break

        embed = discord.Embed(
            title=f"Modrinth Search: {query}",
            description="\n\n".join(lines) + "\n" + "\n".join(queue_lines) + "\n\nSelect from the dropdown to add to the queue. Click 'Download & Install' when ready.",
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
