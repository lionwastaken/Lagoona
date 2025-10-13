# cogs/tickets.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os

logger = logging.getLogger("tickets")

TICKETS_CATEGORY_NAME = os.environ.get("TICKET_CAT_NAME", "Support Tickets")

class TicketCog(commands.Cog, name="TicketCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket", description="Open a support ticket.")
    @app_commands.describe(reason="Brief reason for your ticket")
    async def ticket(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("This command must be used in a server.", ephemeral=True)
            return

        # Find/create category
        category = discord.utils.get(guild.categories, name=TICKETS_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKETS_CATEGORY_NAME)

        # Create channel name
        name = f"ticket-{interaction.user.name}-{interaction.user.discriminator}"
        # Create permission overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        # Add mods from role id if provided
        mod_role_id = os.environ.get("MOD_ROLE_ID")
        if mod_role_id:
            role = guild.get_role(int(mod_role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(name, category=category, overwrites=overwrites, reason="Support ticket created.")
        embed = discord.Embed(title="Support Ticket", description=f"{interaction.user.mention} opened a ticket.\nReason: {reason}", color=discord.Color.blue())
        await channel.send(embed=embed)
        await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
