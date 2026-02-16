import discord
from discord import app_commands
from discord.ext import commands
import os
from src.logger import logger
from src.config import config

# Try to import xai_sdk, handle failure gracefully
try:
    import xai_sdk
    HAS_XAI = True
except ImportError:
    HAS_XAI = False

class AICog(commands.Cog):
    """
    Handles AI integration using xAI's Grok API.
    Provides command-based chat and optional automated interactions.
    """
    def __init__(self, bot):
        self.bot = bot
        self.client = None
        self.setup_client()

    def setup_client(self):
        """Initializes the xAI client if dependencies and API key are present."""
        if not HAS_XAI:
            logger.warning("xai-sdk not installed. AI features disabled.")
            return

        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            logger.warning("XAI_API_KEY not found in environment variables. AI features disabled.")
            return
            
        try:
            self.client = xai_sdk.Client(api_key=api_key)
            logger.info("xAI Client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize xAI Client: {e}")
            self.client = None

    @app_commands.command(name="ai", description="Ask Grok something (Requires API Key)")
    async def ai_chat(self, interaction: discord.Interaction, prompt: str):
        """Sends a prompt to Grok and returns the response."""
        if not self.client:
            await interaction.response.send_message("❌ AI features are not enabled. efficient API key or SDK missing.", ephemeral=True)
            return

        await interaction.response.defer()
        
        try:
            # Construct prompt
            completion = self.client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": "You are a helpful and fully unhinged Minecraft bot assistant. Keep answers short (under 2000 chars)."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            response = completion.choices[0].message.content
            
            if len(response) > 2000:
                response = response[:1990] + "..."
                
            await interaction.followup.send(f"🤖 **Grok says:**\n{response}")
            
        except Exception as e:
            logger.error(f"AI Error: {e}")
            await interaction.followup.send(f"❌ AI Error: {e}", ephemeral=True)

    # Note: Automated triggers are handled by automation.py via shared logic or event bus in future updates.

async def setup(bot):
    await bot.add_cog(AICog(bot))
