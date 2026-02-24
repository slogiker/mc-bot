import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import random
import re
import aiofiles
import os
from src.utils import rcon_cmd, has_role
from src.logger import logger
from src.config import config

COLORS = [discord.Color.blue(), discord.Color.green(), discord.Color.gold(), discord.Color.purple()]

class EconomyCog(commands.Cog):
    """
    Manages the server economy system.
    Features:
    - Balance tracking (stored in `bot_config.json`).
    - /pay and /balance commands.
    - "Word Hunt" minigame: Spawns a word in chat, first to type it wins coins.
    """
    def __init__(self, bot):
        self.bot = bot
        self.word_hunt_active = False
        self.current_word = None
        self.economy_lock = asyncio.Lock()

    async def cog_load(self):
        self.word_hunt_task.start()

    def cog_unload(self):
        self.word_hunt_task.cancel()

    @tasks.loop(minutes=45) 
    async def word_hunt_task(self):
        pass

    @word_hunt_task.before_loop
    async def before_word_hunt(self):
        await self.bot.wait_until_ready()
        # Start the actual random loop logic
        self.bot.loop.create_task(self.random_word_hunt_loop())

    async def random_word_hunt_loop(self):
        while not self.bot.is_closed():
            # Random wait 30-90 mins
            wait_min = random.randint(30, 90)
            logger.info(f"Next Word Hunt in {wait_min} minutes.")
            await asyncio.sleep(wait_min * 60)
            
            bot_config = config.load_bot_config()
            players = bot_config.get('online_players', [])
            if len(players) < 1: # User said >1, but for testing lets say >=1
                logger.info("Skipping Word Hunt: Not enough players.")
                continue

            await self.start_word_hunt()

    async def start_word_hunt(self):
        # Pick a word
        words = ["creeper", "diamond", "netherite", "elytra", "phantom", "redstone", "obsidian", "emerald"]
        self.current_word = random.choice(words)
        self.word_hunt_active = True
        
        # Announce
        msg = f"Word Hunt! First to type '{self.current_word}' wins 100 coins!"
        await rcon_cmd(f'tellraw @a {{"text":"[Bot] {msg}","color":"gold","bold":true}}')
        
        # Monitor chat logs for winner
        try:
            await asyncio.wait_for(self.monitor_chat_for_word(), timeout=60)
        except asyncio.TimeoutError:
            await rcon_cmd('tellraw @a {"text":"[Bot] Word Hunt ended! No one typed it in time.","color":"red"}')
        finally:
            self.word_hunt_active = False
            self.current_word = None

    async def monitor_chat_for_word(self):
        """
        Monitors chat logs via `docker logs -f` for the current word hunt target.
        Stops when:
        - The word is found (Winner awarded).
        - The parent task times out (Game over).
        """
        from src.log_dispatcher import log_dispatcher
        q = log_dispatcher.subscribe()
        await log_dispatcher.start()

        try:
            while self.word_hunt_active:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=1.0)
                    
                    # Regex: <(.*?)> (.*)
                    match = re.search(r'<(.*?)> (.*)', line)
                    if match:
                        player, message = match.groups()
                        
                        if self.current_word.lower() in message.lower():
                            await self.award_winner(player)
                            return

                    # Total timeout check (e.g. 5 mins?) call ended by wait_for wrapper in start_word_hunt
                    
                except asyncio.TimeoutError:
                    continue
                    
        except Exception as e:
            logger.error(f"Word Hunt log reader error: {e}")
        finally:
            log_dispatcher.unsubscribe(q)

    async def award_winner(self, player_name):
        reward = 100
        # bot_config = load_bot_config()
        bot_config = config.load_bot_config()
        economy = bot_config.get('economy', {})
        
        # We need to map player name to discord ID if possible, or store by MC Name?
        # User requested "bot_config['economy'] = {'user_id': balance}".
        # If we only have MC Name, we have to reverse lookup.
        
        user_id = None
        for uid, data in bot_config.get('mappings', {}).items():
            if data.get('name', '').lower() == player_name.lower():
                user_id = uid
                break
        
        if user_id:
            async with self.economy_lock:
                economy[user_id] = economy.get(user_id, 0) + reward
                bot_config['economy'] = economy
                config.save_bot_config(bot_config)
            await rcon_cmd(f'tellraw @a {{"text":"[Bot] {player_name} won the Word Hunt and got {reward} coins!","color":"green"}}')
        else:
            await rcon_cmd(f'tellraw @a {{"text":"[Bot] {player_name} won, but is not linked to Discord! No coins awarded.","color":"yellow"}}')
            logger.warning(f"Word Hunt winner {player_name} has no Discord mapping.")

    @app_commands.command(name="balance", description="Check your or another user's balance")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        bot_config = config.load_bot_config()
        bal = bot_config.get('economy', {}).get(str(target.id), 0)
        
        embed = discord.Embed(title=f"💰 Balance: {target.display_name}", description=f"**{bal}** coins", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pay", description="Pay another user")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
            return
        if user.id == interaction.user.id:
             await interaction.response.send_message("❌ You cannot pay yourself.", ephemeral=True)
             return

        bot_config = config.load_bot_config()
        economy = bot_config.get('economy', {})
        sender_id = str(interaction.user.id)
        receiver_id = str(user.id)
        
        async with self.economy_lock:
            sender_bal = economy.get(sender_id, 0)
            if sender_bal < amount:
                await interaction.response.send_message(f"❌ Insufficient funds. You have {sender_bal} coins.", ephemeral=True)
                return
                
            economy[sender_id] = sender_bal - amount
            economy[receiver_id] = economy.get(receiver_id, 0) + amount
            bot_config['economy'] = economy
            config.save_bot_config(bot_config)
        
        await interaction.response.send_message(f"✅ Paid **{amount}** coins to {user.mention}.", ephemeral=True)
        try:
            await user.send(f"💸 You received **{amount}** coins from {interaction.user.display_name}!")
        except: pass

    @app_commands.command(name="economy_set", description="Set a user's balance (Admin)")
    @has_role("economy_admin")
    async def set_balance(self, interaction: discord.Interaction, user: discord.Member, amount: int):
             
        async with self.economy_lock:
            bot_config = config.load_bot_config()
            economy = bot_config.get('economy', {})
            economy[str(user.id)] = amount
            bot_config['economy'] = economy
            config.save_bot_config(bot_config)
        
        await interaction.response.send_message(f"✅ Set {user.mention}'s balance to **{amount}**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
