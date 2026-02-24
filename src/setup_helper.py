
import discord
from src.config import config
from src.logger import logger

class SetupHelper:
    def __init__(self, bot):
        self.bot = bot

    async def ensure_setup(self, guild: discord.Guild):
        """
        Ensures the guild has the necessary Category, Channels, and Roles.
        Returns a dict of found/created IDs to update the Config.
        """
        logger.info(f"--- Starting Dynamic Setup for Guild: {guild.name} ({guild.id}) ---")
        
        updates = {}
        
        # Define roles to create
        role_definitions = ["MC Admin", "MC Player"]
        
        existing_roles = {r.name: r for r in guild.roles}
        dynamic_roles_config = {}

        for role_name in role_definitions:
            role = existing_roles.get(role_name)
            if not role:
                try:
                    role = await guild.create_role(name=role_name, reason="MC Bot Setup")
                    logger.info(f"Created Role: {role_name}")
                except Exception as e:
                    logger.error(f"Failed to create role {role_name}: {e}")
                    continue
            else:
                logger.info(f"Found Role: {role_name}")
            
            # Special Case: Assign 'MC Admin' to Owner
            if role_name == "MC Admin":
                updates['admin_role_id'] = role.id
                await self._assign_admin_role(guild, role)
            elif role_name == "MC Player":
                updates['player_role_id'] = role.id

        # updates['roles'] is no longer needed as permissions are in user_config by name
        updates['guild_id'] = str(guild.id)
        if guild.owner:
            updates['owner_id'] = guild.owner.id

        # 2. CATEGORY
        cat_name = "Minecraft Server"
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            try:
                category = await guild.create_category(cat_name, reason="MC Bot Setup")
                logger.info(f"Created Category: {cat_name}")
            except Exception as e:
                logger.error(f"Failed to create category {cat_name}: {e}")
        else:
            logger.info(f"Found Category: {cat_name}")

        # 3. CHANNELS
        # Defined as name -> key in config
        channel_defs = {
            "command": "command_channel_id",
            "log": "log_channel_id",
            "debug": "debug_channel_id"
        }
        
        for ch_name, config_key in channel_defs.items():
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            
            # If channel exists but is not in our category, move it? 
            # For simplicity, if it exists, we use it. If not, we create it in the category.
            
            if not channel:
                try:
                    if category:
                        channel = await guild.create_text_channel(ch_name, category=category, reason="MC Bot Setup")
                    else:
                        channel = await guild.create_text_channel(ch_name, reason="MC Bot Setup") # Fallback
                    logger.info(f"Created Channel: {ch_name}")
                except Exception as e:
                    logger.error(f"Failed to create channel {ch_name}: {e}")
                    continue
            else:
                logger.info(f"Found Channel: {ch_name}")
                # Optional: Ensure it's in the correct category
                if category and channel.category != category:
                    try:
                        await channel.edit(category=category)
                        logger.info(f"Moved channel {ch_name} into category {cat_name}")
                    except Exception as e:
                        logger.warning(f"Failed to move channel {ch_name}: {e}")

            updates[config_key] = channel.id

        logger.info("--- Dynamic Setup Completed ---")
        return updates

    async def _assign_admin_role(self, guild, admin_role):
        # 1. Assign to Guild Owner
        if guild.owner:
            if admin_role not in guild.owner.roles:
                try:
                    await guild.owner.add_roles(admin_role, reason="MC Bot Owner")
                    logger.info(f"Assigned {admin_role.name} to Guild Owner: {guild.owner.name}")
                except Exception as e:
                    logger.error(f"Failed to assign role to owner: {e}")
        
        # 2. Assign to anyone with 'Owner' role (heuristic)
        # This covers cases where the bot inviter isn't the server owner but has an "Owner" role
        for member in guild.members:
            if any(r.name.lower() == "owner" for r in member.roles):
                if admin_role not in member.roles:
                     try:
                        await member.add_roles(admin_role, reason="MC Bot Owner Heuristic")
                        logger.info(f"Assigned {admin_role.name} to 'Owner' role holder: {member.name}")
                     except Exception as e:
                        logger.error(f"Failed to assign role to member {member.name}: {e}")
