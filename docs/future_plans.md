# Future Plans: Player Command Design

This document details the planned design and implementation workflow for the `/player` slash command.

## Overview

The `/player` command will allow users to query information about a Minecraft player by username. The command will fetch the player's unique identifier (UUID) and retrieve their skin's face avatar to present in a Discord embed.

## Technical Specifications

### Command Information
- **Name**: `/player`
- **Description**: "Fetch player information and avatar"
- **Arguments**:
  - `username` (string, required): The Minecraft username to query.

### External API Integrations

#### 1. Mojang Profile API
- **Endpoint**: `https://api.mojang.com/users/profiles/minecraft/{username}`
- **Method**: `GET`
- **Response Format**: JSON
- **Fields of Interest**:
  - `id`: The UUID of the player (without hyphens).
  - `name`: The official case-corrected username.
- **Error Handling**:
  - **404 / 204 No Content**: Username does not exist.
  - **429 Too Many Requests**: Rate limit hit.
  - **5xx / Timeout**: API service unavailable.

#### 2. Mineatar Face API
- **Endpoint**: `https://api.mineatar.io/face/{uuid}`
- **Method**: `GET`
- **Response Format**: Image (PNG)
- **Parameters**: Optional sizes or parameters supported by Mineatar (e.g. scale/size).

## Workflow and Execution Steps

```mermaid
sequenceDiagram
    participant User as Discord User
    participant Bot as Discord Bot
    participant Mojang as Mojang API
    participant Mineatar as Mineatar API

    User->>Bot: /player <username>
    Bot->>Bot: Validate username format
    Bot->>Mojang: GET /users/profiles/minecraft/<username>
    alt Username exists
        Mojang-->>Bot: 200 OK (id, name)
        Note over Bot: Construct face URL using UUID
        Bot->>Bot: Build Discord Embed
        Bot-->>User: Send Embed with Face Avatar
    else Username not found
        Mojang-->>Bot: 204 No Content
        Bot-->>User: Error: Player not found
    else API Error
        Mojang-->>Bot: Error / Timeout
        Bot-->>User: Error: Failed to contact Mojang
    end
```

## Proposed Implementation Details

### Discord Embed Structure
- **Title**: Player Profile: `{name}`
- **Thumbnail / Image**: Mineatar Face URL (`https://api.mineatar.io/face/{uuid}`)
- **Fields**:
  - **Official Username**: `{name}`
  - **UUID**: `{uuid}`
  - **Skin Render Link**: Direct URL to view the full skin or raw textures.
- **Footer**: "Data retrieved via Mojang & Mineatar APIs"
- **Color**: Curated Minecraft green or gold theme.

### Example Code Structure (`cogs/player.py`)

```python
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from src.logger import logger

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="player", description="Fetch a Minecraft player profile and head avatar")
    @app_commands.describe(username="Minecraft username to look up")
    async def player(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=False)
        
        # 1. Resolve Username to UUID via Mojang
        mojang_url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(mojang_url) as resp:
                    if resp.status == 204:
                        await interaction.followup.send(f"❌ Player `{username}` not found.", ephemeral=True)
                        return
                    if resp.status != 200:
                        await interaction.followup.send("❌ Mojang API error. Please try again later.", ephemeral=True)
                        return
                    
                    data = await resp.json()
                    uuid = data["id"]
                    corrected_name = data["name"]
            except Exception as e:
                logger.error(f"Error calling Mojang API: {e}")
                await interaction.followup.send("❌ Failed to contact Mojang API.", ephemeral=True)
                return

        # 2. Construct Mineatar Avatar URL
        avatar_url = f"https://api.mineatar.io/face/{uuid}"

        # 3. Build and Send Discord Embed
        embed = discord.Embed(
            title=f"👤 Player Profile: {corrected_name}",
            color=discord.Color.dark_green(),
            url=f"https://namemc.com/profile/{corrected_name}"
        )
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="UUID", value=f"`{uuid}`", inline=False)
        embed.add_field(name="NameMC", value=f"[View Skin/History](https://namemc.com/profile/{corrected_name})", inline=True)
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(PlayerCog(bot))
```
