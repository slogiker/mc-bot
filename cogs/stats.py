
import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import aiofiles
from src.config import config
from src.utils import get_uuid, map_key, display_key, has_role
from src.logger import logger

async def stats_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice]:
    """Provide autocomplete suggestions for the category parameter."""
    try:
        username = interaction.namespace.username
    except AttributeError:
        return []
        
    if not username:
        return []

    # Get UUID (now async)
    uuid = await get_uuid(username)
    if not uuid:
        return []

    stats_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER, 'stats', f"{uuid}.json")
    
    # Use asyncio.to_thread for os.path.exists
    exists = await asyncio.to_thread(os.path.exists, stats_path)
    if not exists:
        return []

    try:
        # Use aiofiles for reading
        async with aiofiles.open(stats_path, 'r') as f:
            content = await f.read()
            stats_data = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load stats for autocomplete: {e}")
        return []

    # Extract and filter categories
    categories = [display_key(key) for key in stats_data.get("stats", {}).keys()]
    if not categories:
        return []

    # Filter based on current input
    current = current.lower()
    matches = [cat for cat in categories if current in cat.lower()][:25]  # Limit to 25 choices

    return [app_commands.Choice(name=cat, value=cat) for cat in matches]

async def item_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice]:
    """Provide autocomplete suggestions for the item parameter based on the selected category."""
    try:
        username = interaction.namespace.username
        category = interaction.namespace.category
    except:
        return []
        
    if not username or not category:
        return []

    # Get UUID and load stats
    uuid = get_uuid(username)
    if not uuid:
        return []

    stats_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER, 'stats', f"{uuid}.json")
    if not os.path.exists(stats_path):
        return []

    try:
        with open(stats_path, 'r') as f:
            stats_data = json.load(f)
    except:
        return []

    # Get items for the selected category
    full_category = map_key(category)
    category_data = stats_data.get("stats", {}).get(full_category, {})
    if not category_data:
        return []

    # Extract and filter items
    items = [display_key(key) for key in category_data.keys()]
    if not items:
        return []

    # Filter based on current input
    current = current.lower()
    matches = [item for item in items if current in item.lower()][:25]  # Limit to 25 choices

    return [app_commands.Choice(name=item, value=item) for item in matches]

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Displays player statistics. Usage: /stats <username> [category] [item]")
    @app_commands.autocomplete(category=stats_autocomplete, item=item_autocomplete)
    @has_role("stats")
    async def stats(self, interaction: discord.Interaction, username: str, category: str = None, item: str = None):
        """Display statistics for a specific player dynamically."""
        try:
            # Get UUID from username (now async)
            uuid = await get_uuid(username)
            if not uuid:
                await interaction.response.send_message(f"❌ Player {username} not found.", ephemeral=True)
                return

            # Construct and check stats file path
            stats_path = os.path.join(config.SERVER_DIR, config.WORLD_FOLDER, 'stats', f"{uuid}.json")
            
            # Use asyncio.to_thread for os.path.exists
            exists = await asyncio.to_thread(os.path.exists, stats_path)
            if not exists:
                await interaction.response.send_message(f"❌ Stats for {username} not found.", ephemeral=True)
                return

            # Load stats JSON using aiofiles
            async with aiofiles.open(stats_path, 'r') as f:
                content = await f.read()
                stats_data = json.loads(content)

            # Handle different cases based on parameters
            if category is None:
                # List all categories dynamically
                categories = [display_key(key) for key in stats_data.get("stats", {}).keys()]
                if not categories:
                    await interaction.response.send_message(f"❌ No stats available for {username}.", ephemeral=True)
                    return
                categories.sort()
                msg = f"📊 Available stats categories for {username}:\n- " + "\n- ".join(categories)
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                full_category = map_key(category)
                category_data = stats_data.get("stats", {}).get(full_category, {})
                if not category_data:
                    await interaction.response.send_message(f"❌ No stats for category '{category}' for {username}.", ephemeral=True)
                    return
                category_display = display_key(full_category)

                if item is None:
                    # List top 10 items in the specified category
                    sorted_items = sorted(category_data.items(), key=lambda x: x[1], reverse=True)[:10]
                    msg = f"📊 Stats for {username} in {category_display}:\n"
                    for item_key, count in sorted_items:
                        item_display = display_key(item_key)
                        msg += f"- {item_display}: {count}\n"
                    if len(category_data) > 10:
                        msg += "... and more\n"
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    # Show specific stat for category:item
                    full_item = map_key(item)
                    stat = category_data.get(full_item, 0)
                    item_display = display_key(full_item)
                    msg = f"{username}'s {category_display}:{item_display}: {stat}"
                    await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            error_msg = f"❌ Failed to get stats: {e}"
            logger.error(error_msg, exc_info=True)
            await interaction.response.send_message(error_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Stats(bot))
