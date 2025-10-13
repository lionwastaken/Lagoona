# utils/interaction_helpers.py
import discord
import asyncio
import io
import logging

logger = logging.getLogger("interaction_helpers")

async def safe_respond(interaction: discord.Interaction, embed: discord.Embed=None, content: str=None, file: discord.File=None, ephemeral: bool=False):
    """
    Defer, then followup safely. Use for long-running operations or when building files.
    """
    try:
        # defer when not already responded
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception as e:
        logger.debug("Defer failed or already deferred: %s", e)

    try:
        kwargs = {}
        if content:
            kwargs['content'] = content
        if embed:
            kwargs['embed'] = embed
        if file:
            kwargs['files'] = [file]
        await interaction.followup.send(**kwargs, ephemeral=ephemeral)
    except discord.errors.NotFound:
        # interaction expired — fallback to channel send if possible
        try:
            if interaction.channel:
                await interaction.channel.send(content=content, embed=embed, file=file)
        except Exception as e:
            logger.exception("Fallback send failed: %s", e)
    except Exception as e:
        logger.exception("Failed to send followup: %s", e)
