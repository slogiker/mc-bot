#!/usr/bin/env python3
"""
Auto-setup script for Discord Bot
Creates roles, channels, and maps IDs to config automatically during installation
"""

import discord
import asyncio
import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.logger import logger

async def auto_setup(bot_token: str, guild_id: int):
    """
    Automatically create roles and channels for the bot
    
    Args:
        bot_token: Discord bot token
        guild_id: Guild ID to set up
    """
    
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    
    client = discord.Client(intents=intents)
    
    setup_complete = asyncio.Event()
    results = {}
    
    @client.event
    async def on_ready():
        try:
            print(f"✅ Connected as {client.user}")
            
            guild = client.get_guild(guild_id)
            if not guild:
                print(f"❌ Could not find guild with ID {guild_id}")
                print(f"   Bot is in {len(client.guilds)} guild(s)")
                for g in client.guilds:
                    print(f"   - {g.name} (ID: {g.id})")
                await client.close()
                return
            
            print(f"✅ Found guild: {guild.name}")
            
            # Create roles
            print("\n📋 Creating roles...")
            owner_role = await guild.create_role(
                name="Owner",
                color=discord.Color.red(),
                hoist=True,
                mentionable=True,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created role: Owner (ID: {owner_role.id})")
            
            admin_role = await guild.create_role(
                name="Admin",
                color=discord.Color.orange(),
                hoist=True,
                mentionable=True,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created role: Admin (ID: {admin_role.id})")
            
            player_role = await guild.create_role(
                name="Player",
                color=discord.Color.green(),
                hoist=True,
                mentionable=True,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created role: Player (ID: {player_role.id})")
            
            # Create channels
            print("\n📁 Creating channels...")
            
            # Permission overrides
            bot_member = guild.me
            overrides_read_only = {
                guild.default_role: discord.PermissionOverwrite(send_messages=False, add_reactions=False),
                bot_member: discord.PermissionOverwrite(send_messages=True, embed_links=True, attach_files=True)
            }
            
            overrides_normal = {
                guild.default_role: discord.PermissionOverwrite(read_messages=True),
                bot_member: discord.PermissionOverwrite(send_messages=True, embed_links=True, attach_files=True)
            }
            
            # Commands channel
            commands_channel = await guild.create_text_channel(
                name="commands",
                topic="Use bot commands here",
                overwrites=overrides_normal,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created channel: #commands (ID: {commands_channel.id})")
            
            # Console channel (logs)
            console_channel = await guild.create_text_channel(
                name="console",
                topic="Live server logs",
                overwrites=overrides_read_only,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created channel: #console (ID: {console_channel.id})")
            
            # Debug channel
            debug_channel = await guild.create_text_channel(
                name="debug",
                topic="Debug messages and event notifications",
                overwrites=overrides_read_only,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created channel: #debug (ID: {debug_channel.id})")
            
            # Server info channel
            info_channel = await guild.create_text_channel(
                name="server-information",
                topic="Server details and status",
                overwrites=overrides_read_only,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created channel: #server-information (ID: {info_channel.id})")
            
            # Backups channel
            backups_channel = await guild.create_text_channel(
                name="backups",
                topic="Server backup notifications",
                overwrites=overrides_read_only,
                reason="Auto-setup by bot installer"
            )
            print(f"   ✅ Created channel: #backups (ID: {backups_channel.id})")
            
            # Save to config
            print("\n💾 Saving configuration...")
            bot_config = config.load_bot_config()
            bot_config.update({
                'guild_id': guild_id,
                'command_channel_id': commands_channel.id,
                'log_channel_id': console_channel.id,
                'debug_channel_id': debug_channel.id,
                'info_channel_id': info_channel.id,
                'backup_channel_id': backups_channel.id,
            })
            config.save_bot_config(bot_config)
            print("   ✅ Configuration saved")
            
            # Store results
            results['success'] = True
            results['channels'] = {
                'commands': commands_channel.id,
                'console': console_channel.id,
                'debug': debug_channel.id,
                'server-information': info_channel.id,
                'backups': backups_channel.id
            }
            results['roles'] = {
                'Owner': owner_role.id,
                'Admin': admin_role.id,
                'Player': player_role.id
            }
            
            print("\n✅ Auto-setup completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Error during setup: {e}")
            import traceback
            traceback.print_exc()
            results['success'] = False
            results['error'] = str(e)
        
        finally:
            setup_complete.set()
            await client.close()
    
    # Start bot
    try:
        await client.start(bot_token)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        results['success'] = False
        results['error'] = str(e)
    
    # Wait for setup to complete
    await setup_complete.wait()
    
    return results

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python auto_setup.py <bot_token> <guild_id>")
        sys.exit(1)
    
    bot_token = sys.argv[1]
    guild_id = int(sys.argv[2])
    
    result = asyncio.run(auto_setup(bot_token, guild_id))
    
    if result.get('success'):
        print("\n" + "="*50)
        print("SETUP SUMMARY")
        print("="*50)
        print("\nChannels created:")
        for name, ch_id in result['channels'].items():
            print(f"  - #{name}: {ch_id}")
        print("\nRoles created:")
        for name, role_id in result['roles'].items():
            print(f"  - {name}: {role_id}")
        print("\nConfiguration has been saved to data/bot_config.json")
        print("="*50)
        sys.exit(0)
    else:
        print(f"\n❌ Setup failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
