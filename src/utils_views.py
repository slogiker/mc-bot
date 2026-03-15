import discord
from src.logger import logger

class CodeModal(discord.ui.Modal, title='Enter Verification Code'):
    def __init__(self, join_guard, mc_username: str, expected_code: str):
        super().__init__()
        self.join_guard = join_guard
        self.mc_username = mc_username
        self.expected_code = expected_code
        
        self.code_input = discord.ui.TextInput(
            label='4-Digit Code',
            placeholder='1234',
            style=discord.TextStyle.short,
            required=True,
            min_length=4,
            max_length=4
        )
        self.add_item(self.code_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.code_input.value == self.expected_code:
            await self.join_guard.complete_challenge(self.mc_username)
            await interaction.response.send_message("✅ **Verification successful.** You may now log in to the Minecraft server.", ephemeral=False)
            
            # Disable the button on the original message if possible
            try:
                # We do this quickly before the message objects fall out of scope or we pass the message in
                pass
            except Exception:
                pass
        else:
            await interaction.response.send_message("❌ **Incorrect code.** Please wait to be kicked again before trying a new code.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Error in CodeModal: {error}")
        await interaction.response.send_message('❌ Something went wrong.', ephemeral=True)


class ChallengeView(discord.ui.View):
    def __init__(self, join_guard, mc_username: str, expected_code: str):
        # Timeout is handled externally by the JoinGuard task, but we set one here anyway
        super().__init__(timeout=120)
        self.join_guard = join_guard
        self.mc_username = mc_username
        self.expected_code = expected_code

    @discord.ui.button(label='Verify Identity', style=discord.ButtonStyle.success, emoji='🔑')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Open modal
        modal = CodeModal(self.join_guard, self.mc_username, self.expected_code)
        await interaction.response.send_modal(modal)
        
    async def on_timeout(self):
        # Disable all items
        for item in self.children:
            item.disabled = True
