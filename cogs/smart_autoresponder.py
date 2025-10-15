# cogs/smart_autoresponder.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp, asyncio, os, re, logging, random

logger = logging.getLogger("smart_autoresponder")

AUTO_ENABLED = set()

# --- topic filters ---
BANNED_TOPICS = ("politic", "religion", "church", "bible", "islam", "christian",
                 "atheis", "football", "soccer", "nba", "cricket", "hockey")

# --- image list for embeds / cards (update with your two URLs) ---
ANNOUNCEMENT_IMAGES = [
    "https://i.postimg.cc/28fmdWX2/officialbanner.png",
    "https://i.postimg.cc/PrkhbDF7/SGStudio-Banner-Edited.png",
]

# -----------------------------------------------------------
async def query_llm(prompt: str) -> str:
    """Query Gemini or ChatGPT; limited to technical/Roblox topics."""
    gemini = os.getenv("GEMINI_API_KEY")
    openai = os.getenv("CHATGPT_API_KEY")
    try:
        async with aiohttp.ClientSession() as s:
            if gemini:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={gemini}"
                body = {
                    "contents": [{
                        "parts": [{
                            "text":
                                ("Answer only technical, studio-related or Roblox questions. "
                                 "Decline or redirect any unrelated, political, sports or religious topics. "
                                 "Keep tone friendly, helpful, lively, short. "
                                 f"User: {prompt}")
                        }]
                    }]
                }
                async with s.post(url, json=body) as r:
                    data = await r.json()
                    return (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "🌊 I didn’t catch that, can you rephrase?")
                    )

            elif openai:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {openai}"}
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system",
                         "content": ("You are Lagoona, a lively technical assistant for a Roblox Studio server. "
                                     "Answer clearly and with enthusiasm. "
                                     "Only discuss Roblox, scripting, building, design, or studio-related questions. "
                                     "If asked about politics, sports, or religion, respond: "
                                     "'That’s outside the studio’s scope 🌊 let's keep it on Roblox or dev topics!'")},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.9,
                }
                async with s.post(url, headers=headers, json=payload) as r:
                    d = await r.json()
                    if "choices" in d:
                        return d["choices"][0]["message"]["content"].strip()
                    logger.warning("ChatGPT response: %s", d)
                    return "🌊 My mind’s drifting; try again?"

        return "LLM keys not configured."
    except Exception as e:
        logger.exception("LLM error: %s", e)
        return "💫 The currents are noisy; try again soon!"
# -----------------------------------------------------------

class SmartResponder(commands.Cog):
    """Smarter auto-responder restricted to studio / Roblox topics."""

    def __init__(self, bot):
        self.bot = bot

    # Toggle
    @app_commands.command(name="autorespond", description="Toggle Lagoona auto-response for this channel.")
    @app_commands.describe(mode="on_or_off")
    async def autorespond(self, inter: discord.Interaction, mode: str):
        mode = mode.lower()
        cid = inter.channel.id
        if mode == "on":
            AUTO_ENABLED.add(cid)
            await inter.response.send_message("✅ Auto-respond enabled here.", ephemeral=True)
        elif mode == "off":
            AUTO_ENABLED.discard(cid)
            await inter.response.send_message("❎ Auto-respond disabled.", ephemeral=True)
        else:
            await inter.response.send_message("Use `/autorespond on` or `/autorespond off`.", ephemeral=True)

    # Listen
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot:
            return

        # Skip announcement channels
        if getattr(msg.channel, "is_news", lambda: False)():
            # react to new messages automatically
            for emoji in ("⭐", "💛", "🫶"):
                try: await msg.add_reaction(emoji)
                except Exception: pass
            return

        if msg.channel.id not in AUTO_ENABLED:
            return

        content = msg.content.strip()
        if not content:
            return

        # Filter banned topics before sending to API
        lowered = content.lower()
        if any(t in lowered for t in BANNED_TOPICS):
            await msg.reply("Let's keep it about Roblox and the studio 🌊")
            return

        async with msg.channel.typing():
            reply = await query_llm(content)
            await asyncio.sleep(0.3)

        try:
            await msg.reply(f"{msg.author.mention} {reply}")
        except Exception as e:
            logger.warning("Reply failed: %s", e)

    # Add random image to Lagoona's embeds / cards
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # Example: if Lagoona posts embeds elsewhere, decorate them
        if after.author == self.bot.user and after.embeds:
            for embed in after.embeds:
                embed.set_image(url=random.choice(ANNOUNCEMENT_IMAGES))
            try:
                await after.edit(embeds=after.embeds)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(SmartResponder(bot))
