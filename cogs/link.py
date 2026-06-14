import discord
from discord import app_commands
from discord.ext import commands
from src.mc_link_manager import MCLinkManager
from src.mojang import verify_premium_mc_account
from src.logger import logger
from src.utils import has_role


class Link(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.link_manager = MCLinkManager()

    # ── /link ─────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="link",
        description="Povezi svoj Discord racun z Minecraft uporabniskim imenom"
    )
    @app_commands.describe(username="Tvoje tocno Minecraft uporabnisko ime")
    async def link_cmd(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            existing = await self.link_manager.get_link_by_mc(username)
            if existing and existing["discord_id"] != interaction.user.id:
                await interaction.followup.send(
                    f"Uporabnisko ime **{username}** je ze povezano z drugim Discord racunom. "
                    "Ce gre za napako, kontaktiraj admina.",
                    ephemeral=True
                )
                return

            current = await self.link_manager.get_link_by_discord(interaction.user.id)
            replacement_notice = ""
            if current:
                old_name = current["mc_username"]
                if old_name.lower() == username.lower():
                    await interaction.followup.send(
                        f"Tvoj racun je ze povezan z **{username}**.",
                        ephemeral=True
                    )
                    return
                replacement_notice = f"\n*(Zamenjuje prejsnjo povezavo z **{old_name}**)*"

            is_premium = await verify_premium_mc_account(username)
            await self.link_manager.link_account(interaction.user.id, username, is_premium)

            if is_premium:
                status = (
                    "Premium racun zaznan. "
                    "Mojang API je potrdil tvojo identiteto — verifikacijska koda ni potrebna."
                )
            else:
                status = (
                    "Cracked / offline racun zaznan. "
                    "Ko se prilogis po vec kot 30 minutah odsotnosti, bos dobil kodo "
                    "na kick screenu. Vtipkaj /verify <koda> v #commands."
                )

            await interaction.followup.send(
                f"Discord uspesno povezan z Minecraft racunom **{username}**.\n\n"
                f"{status}{replacement_notice}",
                ephemeral=True
            )
            logger.info(f"{interaction.user.name} linked MC account {username} (premium={is_premium})")

        except Exception as e:
            logger.error(f"Error in /link: {e}", exc_info=True)
            await interaction.followup.send("Nepricakovana napaka. Preveri bot loge.", ephemeral=True)

    # ── /verify ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="verify",
        description="Potrdi svojo identiteto z verifikacijsko kodo (dobis jo na kick screenu)"
    )
    @app_commands.describe(code="6-znakovna koda iz kick sporocila")
    async def verify_cmd(self, interaction: discord.Interaction, code: str):
        guard = self.bot.join_guard

        if not guard:
            await interaction.response.send_message(
                "JoinGuard ni aktiven. Kontaktiraj admina.",
                ephemeral=True
            )
            return

        success, message = await guard.verify_code(interaction.user.id, code)
        await interaction.response.send_message(message, ephemeral=True)

    # ── /unlink ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="unlink",
        description="Odstrani povezavo med tvojim Discord in Minecraft racunom"
    )
    async def unlink_cmd(self, interaction: discord.Interaction):
        success = await self.link_manager.unlink_account(interaction.user.id)
        if success:
            await interaction.response.send_message(
                "Minecraft racun uspesno odklenjen.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Nimas povezanega Minecraft racuna.", ephemeral=True
            )

    # ── /linked ───────────────────────────────────────────────────────────────

    @app_commands.command(
        name="linked",
        description="Preveri katero Minecraft ime je povezano s tvojim Discord racunom"
    )
    async def linked_cmd(self, interaction: discord.Interaction):
        entry = await self.link_manager.get_link_by_discord(interaction.user.id)
        if not entry:
            await interaction.response.send_message(
                "Nimas povezanega Minecraft racuna. Uporabi /link <username>.",
                ephemeral=True
            )
            return

        import time
        grace_remaining = ""
        lv = entry.get("last_verified")
        if lv:
            remaining = (lv + 1800) - time.time()
            if remaining > 0:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                grace_remaining = f"\nGrace window: se **{mins}m {secs}s**"

        account_type = "Premium" if entry.get("is_premium") else "Cracked/Offline"

        await interaction.response.send_message(
            f"**Minecraft racun:** `{entry['mc_username']}`\n"
            f"**Tip racuna:** {account_type}"
            f"{grace_remaining}",
            ephemeral=True
        )

    # ── /unlink_admin ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="unlink_admin",
        description="[Admin] Prisilno odstrani Discord-MC povezavo"
    )
    @app_commands.describe(
        discord_user="Discord uporabnik katerega povezavo zelis odstraniti",
        mc_username="ALI Minecraft uporabnisko ime"
    )
    @has_role("cmd")
    async def unlink_admin_cmd(
        self,
        interaction: discord.Interaction,
        discord_user: discord.Member | None = None,
        mc_username: str | None = None
    ):
        if not discord_user and not mc_username:
            await interaction.response.send_message(
                "Podaj Discord uporabnika ALI Minecraft username.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        target_id = None
        if discord_user:
            target_id = discord_user.id
        elif mc_username:
            link = await self.link_manager.get_link_by_mc(mc_username)
            if link:
                target_id = link["discord_id"]

        if target_id:
            success = await self.link_manager.unlink_account(target_id)
            if success:
                await interaction.followup.send("Povezava uspesno odstranjena.", ephemeral=True)
            else:
                await interaction.followup.send("Zapis ne obstaja.", ephemeral=True)
        else:
            await interaction.followup.send("Ni najden noben zapis za ta vhod.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Link(bot))
