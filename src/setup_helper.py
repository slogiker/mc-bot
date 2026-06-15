
import discord
from src.config import config
from src.logger import logger

class SetupHelper:
    def __init__(self, bot):
        self.bot = bot

    async def ensure_setup(self, guild: discord.Guild):
        """
        Ensures the guild has the necessary Category, Channels, and Roles.
        Self-healing: Reconciles missing items and repairs configuration.
        """
        logger.debug(f"--- Starting Self-Healing Setup for Guild: {guild.name} ---")
        
        updates = {}
        
        # 1. ROLES RECONCILIATION
        role_definitions = ["Owner", "MC Admin", "MC Player"]
        existing_roles = {r.name: r for r in guild.roles}

        for role_name in role_definitions:
            role = existing_roles.get(role_name)
            if not role:
                try:
                    # Create missing role with specific color
                    if role_name == "Owner":
                        color = discord.Color.red()
                    elif role_name == "MC Admin":
                        color = discord.Color.gold()
                    else:
                        color = discord.Color.blue()
                    role = await guild.create_role(name=role_name, color=color, reason="Self-Healing: Role missing")
                    logger.info(f"Self-Healer: Created missing Role: {role_name}")
                except Exception as e:
                    logger.error(f"Failed to create role {role_name}: {e}")
                    continue
            
            # Map IDs to config keys
            if role_name == "Owner":
                updates['owner_role_id'] = role.id
                await self._assign_owner_role(guild, role)
            elif role_name == "MC Admin":
                updates['admin_role_id'] = role.id
            elif role_name == "MC Player":
                updates['player_role_id'] = role.id

        # 2. CATEGORY RECONCILIATION
        cat_name = "Minecraft Server"
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            try:
                category = await guild.create_category(cat_name, reason="Self-Healing: Category missing")
                logger.info(f"Self-Healer: Created missing Category: {cat_name}")
            except Exception as e:
                logger.error(f"Failed to create category {cat_name}: {e}")
        
        # 3. CHANNELS RECONCILIATION
        channel_defs = {
            "command": "command_channel_id",
            "log": "log_channel_id",
            "debug": "debug_channel_id"
        }
        
        for ch_name, config_key in channel_defs.items():
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            
            if not channel:
                try:
                    channel = await guild.create_text_channel(
                        ch_name, 
                        category=category, 
                        reason="Self-Healing: Channel missing"
                    )
                    logger.info(f"Self-Healer: Created missing Channel: {ch_name}")
                except Exception as e:
                    logger.error(f"Failed to create channel {ch_name}: {e}")
                    continue
            else:
                # Ensure existing channel is in the right category
                if category and channel.category_id != category.id:
                    try:
                        await channel.edit(category=category)
                        logger.info(f"Self-Healer: Restored channel {ch_name} to category {cat_name}")
                    except Exception as e:
                        logger.warning(f"Failed to move channel {ch_name}: {e}")

            updates[config_key] = channel.id

        updates['guild_id'] = guild.id
        if guild.owner:
            updates['owner_id'] = guild.owner.id

        logger.debug("--- Self-Healing Setup Completed ---")
        return updates

    async def _assign_owner_role(self, guild, owner_role):
        # 1. Assign to Guild Owner
        if guild.owner:
            if owner_role not in guild.owner.roles:
                try:
                    await guild.owner.add_roles(owner_role, reason="MC Bot Owner")
                    logger.info(f"Assigned {owner_role.name} to Guild Owner: {guild.owner.name}")
                except Exception as e:
                    logger.error(f"Failed to assign role to owner: {e}")
        
        # 2. Assign to anyone with an existing 'Owner' role (heuristic)
        for member in guild.members:
            if any(r.name.lower() == "owner" and r.id != owner_role.id for r in member.roles):
                if owner_role not in member.roles:
                     try:
                        await member.add_roles(owner_role, reason="MC Bot Owner Heuristic")
                        logger.info(f"Assigned {owner_role.name} to existing 'Owner' role holder: {member.name}")
                     except Exception as e:
                        logger.error(f"Failed to assign role to member {member.name}: {e}")
