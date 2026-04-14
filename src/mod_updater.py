import os
import re
import shutil
import aiohttp
import asyncio
import zipfile
import json
from collections import deque
from datetime import datetime
from src.config import config
from src.logger import logger

class ModUpdater:
    def __init__(self, callback=None):
        self.api_base = "https://api.modrinth.com/v2"
        self.callback = callback
        
        # Hardcoded overrides from user script
        self.mod_id_overrides = {
            "voicechat": "simple-voice-chat",
            "voicechat-fabric": "simple-voice-chat",
        }
        
        # Determine whether to look in plugins/ or mods/ based on what exists
        self.target_dir = os.path.join(config.SERVER_DIR, "plugins")
        self.is_paper = True
        
        if not os.path.exists(self.target_dir):
            self.target_dir = os.path.join(config.SERVER_DIR, "mods")
            self.is_paper = False
            
    async def _send_status(self, msg):
        logger.info(f"ModUpdater: {msg}")
        if self.callback:
            try:
                await self.callback(msg)
            except Exception:
                pass

    async def _get_project_from_id(self, session, project_id):
        if not project_id: return None
        url = f"{self.api_base}/project/{project_id}"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return None

    async def _search_project_by_name(self, session, query):
        if not query: return None
        url = f"{self.api_base}/search"
        params = {"query": query, "limit": 1}
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    hits = (await resp.json()).get("hits", [])
                    return hits[0] if hits else None
        except Exception:
            pass
        return None

    def _find_modrinth_project_sync(self, jar_path, filename):
        mod_id = None
        # Try metadata (Fabric/Quilt json, Paper plugin.yml)
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                if 'fabric.mod.json' in jar.namelist():
                    with jar.open('fabric.mod.json') as meta_file:
                        data = json.load(meta_file)
                        mod_id = data.get('custom', {}).get('modrinth') or data.get('id')
                elif 'plugin.yml' in jar.namelist():
                    # For paper/spigot, we often just read the name out of plugin.yml
                    with jar.open('plugin.yml') as meta_file:
                        lines = meta_file.readlines()
                        for line in lines:
                            text = line.decode('utf-8', errors='ignore')
                            if text.startswith('name:'):
                                mod_id = text.split(':', 1)[1].strip()
                                break
        except Exception:
            pass

        if not mod_id:
            # Fallback regex strip
            mod_id = re.sub(r'[-_.]?(fabric|forge|quilt|neo\w*|paper|spigot|bukkit)[-_.]?', '', filename.lower().removesuffix(".jar"))
            mod_id = re.split(r'[-_.]?\d', mod_id, 1)[0].strip("-._")

        if mod_id in self.mod_id_overrides:
            mod_id = self.mod_id_overrides[mod_id]
            
        return mod_id

    async def _get_mod_versions(self, session, project_id):
        url = f"{self.api_base}/project/{project_id}/version"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return []

    def _filter_versions(self, versions, game_version, loader):
        candidates = [v for v in versions if game_version in v.get("game_versions", []) and loader in v.get("loaders", [])]
        if not candidates: 
            return []
        release_versions = [v for v in candidates if v.get("version_type") == "release"]
        return release_versions if release_versions else candidates

    async def _download_version(self, session, version_info, target_dir):
        primary_file = next((f for f in version_info.get("files", []) if f.get("primary")), None)
        if not primary_file:
            # Fallback to first file
            primary_file = version_info.get("files", [None])[0]
            
        if not primary_file:
            return False, "No file found"

        fname = primary_file.get("filename")
        outpath = os.path.join(target_dir, fname)
        
        try:
            async with session.get(primary_file.get("url")) as resp:
                if resp.status == 200:
                    with open(outpath, "wb") as f:
                        f.write(await resp.read())
                    return True, fname
        except Exception as e:
            return False, str(e)
            
        return False, "Download failed"

    async def update_all(self, game_version, loader=None, is_setup=False):
        """
        Main execution flow.
        Runs through the mods folder, identifies all jars, backs them up, and replaces them with updated dependencies.
        """
        if not os.path.exists(self.target_dir):
            await self._send_status("❌ Target directory not found. Is the server fully setup?")
            return False

        if not loader:
            loader = "paper" if self.is_paper else "fabric"

        local_mods = [f for f in os.listdir(self.target_dir) if f.endswith(".jar")]
        if not local_mods:
            await self._send_status(f"ℹ️ No existing `.jar` files found in `{self.target_dir}` to update.")
            return True

        if is_setup:
            await self._send_status(f"🔍 Analyzing **{len(local_mods)}** foundational files...")
        else:
            await self._send_status(f"🔍 Analyzing **{len(local_mods)}** local files...")
        
        # 1. Backup old files
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        backup_dir = os.path.join(config.SERVER_DIR, f"old_mods_{timestamp}")
        
        if not is_setup:
            os.makedirs(backup_dir, exist_ok=True)
            for filename in local_mods:
                old_path = os.path.join(self.target_dir, filename)
                new_path = os.path.join(backup_dir, filename)
                shutil.move(old_path, new_path)
            await self._send_status(f"📦 Moved old files to `old_mods_{timestamp}/`")
            scan_dir = backup_dir
        else:
            scan_dir = self.target_dir

        summary = {}
        mods_to_process = deque()
        processed_or_queued = set()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            # 2. Identify projects from backed-up (or local) jars
            for filename in local_mods:
                jar_path = os.path.join(scan_dir, filename)
                mod_id = await asyncio.to_thread(self._find_modrinth_project_sync, jar_path, filename)
                
                project = await self._get_project_from_id(session, mod_id)
                if not project:
                    project = await self._search_project_by_name(session, mod_id)
                    
                if project and project.get("slug"):
                    slug = project["slug"]
                    title = project.get("title", slug)
                    if slug not in processed_or_queued:
                        mods_to_process.append(slug)
                        processed_or_queued.add(slug)
                        summary[slug] = {"title": title, "status": "Queued", "version": "---"}
                else:
                    summary[filename] = {"title": filename, "status": "Not Found", "version": "---"}
                    
            if is_setup:
                await self._send_status(f"📡 Installing foundational mods for Minecraft `{game_version}` ({loader})...")
            else:
                await self._send_status(f"📡 Downloading updates for Minecraft `{game_version}` ({loader})...")

            # 3. Process the queue (including discovered dependencies)
            updated_count = 0
            while mods_to_process:
                slug = mods_to_process.popleft()
                project_title = summary[slug]["title"]
                
                versions = await self._get_mod_versions(session, slug)
                candidates = self._filter_versions(versions, game_version, loader)
                
                if not candidates:
                    summary[slug].update({"status": "Incompatible", "version": "N/A"})
                    continue
                    
                latest = candidates[0]
                ver_num = latest.get("version_number", "Unknown")
                
                success, fname_or_err = await self._download_version(session, latest, self.target_dir)
                if success:
                    summary[slug].update({"status": "Updated", "version": ver_num})
                    updated_count += 1
                else:
                    summary[slug].update({"status": "Failed", "version": "N/A"})
                    
                # 4. Check array of dependencies
                for dep in latest.get("dependencies", []):
                    if dep.get("dependency_type") == "required":
                        dep_slug = dep.get("project_id")
                        if dep_slug and dep_slug not in processed_or_queued:
                            dep_details = await self._get_project_from_id(session, dep_slug)
                            dep_title = dep_details.get("title", dep_slug) if dep_details else dep_slug
                            
                            mods_to_process.append(dep_slug)
                            processed_or_queued.add(dep_slug)
                            summary[dep_slug] = {"title": dep_title, "status": "Dep Queued", "version": "---"}
                            
        if is_setup:
            await self._send_status(f"✨ Installation complete! Downloaded **{updated_count}** `.jar` files.")
        else:
            await self._send_status(f"✨ Update complete! Successfully downloaded **{updated_count}** new `.jar` files.")
        
        # Format the summary for discord (truncate if too long)
        final_msg = "```\nUpdate Summary:\n"
        for item in summary.values():
            status = item["status"]
            name = item["title"][:30]
            ver = item["version"][:15]
            final_msg += f"{name:<32} | {status:<12} | {ver}\n"
        final_msg += "```"
        
        if len(final_msg) <= 2000:
             await self._send_status(final_msg)
             
        return True
