# Developer Guide

Welcome to the MC-Bot Developer Guide! This document provides an overview of the core architecture and a step-by-step tutorial on how to extend the bot by creating your own Discord Cog.

## 🏗️ Core Architecture

MC-Bot is designed to run entirely within a single Docker container. Here is a high-level overview of how the components interact:

- **Discord Bot (Python):** The brain of the operation, built with `discord.py`. It handles commands, permissions, and interacts with the Minecraft server.
- **Minecraft Server:** Runs as a background process within the same Docker container, managed via `tmux`.
- **RCON Communication:** The bot communicates with the Minecraft server using the RCON protocol (Restricted to `localhost`). This allows the bot to send commands securely without exposing RCON to the internet.
- **Log Streaming:** The bot reads the Minecraft server's console output live using a `tail -F` mechanism, allowing it to stream logs directly to Discord and parse player events (e.g., joins, leaves, deaths).

---

## 🛠️ Tutorial: Creating a Custom Cog

In `discord.py`, a "Cog" is a module that groups related commands and events. We will create a simple `PingCog` that responds with the bot's latency and basic server status.

### Step 1: Create the Cog File

Create a new file in the `bot/cogs/` directory (or wherever cogs are stored) named `ping_cog.py`.

```python
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger("PingCog")

class PingCog(commands.Cog):
    """A simple Cog for checking bot latency."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Replies with pong and the bot latency.")
    async def ping_command(self, interaction: discord.Interaction):
        # Calculate the latency in milliseconds
        latency = round(self.bot.latency * 1000)
        
        # Respond to the user
        await interaction.response.send_message(f"🏓 Pong! Latency: `{latency}ms`", ephemeral=True)

# The setup function is required for discord.py to load the Cog
async def setup(bot):
    await bot.add_cog(PingCog(bot))
    logger.info("PingCog loaded.")
```

### Step 2: Tie it into the Architecture

To ensure your new Cog works within the MC-Bot architecture:

1. **Permissions:** You might want to restrict who can use this command. You can do this by using the `@app_commands.checks.has_permissions(...)` decorator or MC-Bot's custom permission decorators if applicable.
2. **Loading the Cog:** MC-Bot usually loads all cogs dynamically from a specified directory (e.g., `bot/cogs/`). If your bot loads cogs explicitly in `main.py` or a dedicated cog-loader, be sure to add `'cogs.ping_cog'` to the list of loaded extensions.
3. **Interacting with Minecraft:** If your command needed to talk to the server, you would inject or access the RCON manager (typically available via `self.bot.rcon` or a similar service class).

### Step 3: Test Your Command

1. Restart the Docker container (`make restart` or docker commands).
2. The bot will automatically sync slash commands with Discord upon startup.
3. Go to your Discord server and type `/ping`.

### Conclusion

You've successfully created a new command! From here, you can explore the codebase to see how existing commands (like `/start` or `/logs`) interact with the RCON system and Docker environment to build more complex features.
