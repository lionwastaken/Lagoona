# cogs/smart_autoresponder.py
import discord
from discord.ext import commands
import aiohttp, asyncio, os, logging, random

logger = logging.getLogger("smart_autoresponder")

BANNERS = [
    "https://example.com/lagoona_banner1.png",   # replace with your first image URL
    "https://example.com/lagoona_banner2.png",   # replace with your second image URL
]

BANNED_TOPICS = (
    "politic", "religion", "church", "bible", "islam", "christian",
    "atheis", "football", "soccer", "nba", "cricket", "hockey"
)


# -------------------------------------------------
async def call_llm(prompt: str) -> str:
    """Query Gemini or ChatGPT with restricted topic scope."""
    gemini = os.getenv("GEMINI_API_KEY")
    openai = os.getenv("CHATGPT_API_KEY")

    try:
        async with aiohttp.ClientSession() as s:
            # ---- GEMINI ----
            if gemini:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-pro:generateContent?key={gemini}"
                )
                body = {
                    "contents": [{
                        "parts": [{
                            "text": (
                                "You are Lagoona, a lively Roblox Studio assistant. "
                                "Answer only technical, creative-studio, or Roblox-related questions. "
                                "If the user asks about politics, religion, or sports, "
                                "say 'That’s outside the studio’s scope 🌊 let's keep it on Roblox topics!' "
                                f"User: {prompt}"
                            )
                        }]
                    }]
                }
                async with s.post(url, json=body) as r:
                    d = await r.json()
                    return (
                        d.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "🌊 Hmm, can you rephrase that?")
                    )

            # ---- CHATGPT ----
            elif openai:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {openai}"}
                payload = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system",
                         "content": (
                             "You are Lagoona, a lively Roblox Studio assistant. "
                             "Only discuss scripting, building, design, or studio questions. "
                             "Avoid politics, religion, or sports. "
                             "Politely redirect off-topic chats. "
                             "Use cheerful, short answers with emojis sometimes."
                         )},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.9,
                }
                async with s.post(url, headers=headers, json=payload) as r:
                    d = await r.json()
                    if "choices" in d:
                        return d["choices"][0]["message"]["content"].strip()
                    return "🌊 My thoughts got swept away—try again?"
        return "LLM key not configured."
    except Exception as e:
        logger.exception("LLM error: %s", e)
        return "💫 The waves are noisy—try again later!"
# -------------------------------------------------


class SmartResponder(commands.Cog):
    """Auto-reacts in announcement channels and replies when Lagoona is mentioned."""

    def __init__(self, bot):
        self.bot = bot

    # --- handle all incoming messages ---
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        # Ignore bots or DMs
        if not msg.guild or msg.author.bot:
            return

        # 1️⃣ Announcement channels — react only
        if getattr(msg.channel, "is_news", lambda: False)():
            for emoji in ("⭐", "💛", "🫶"):
                try:
                    await msg.add_reaction(emoji)
                    await asyncio.sleep(0.4)  # rate-limit safety
                except Exception:
                    pass
            return

        # 2️⃣ Normal chat — reply when Lagoona mentioned
        content_lower = msg.content.lower()
        if not content_lower:
            return

        if self.bot.user and (self.bot.user.mentioned_in(msg) or "lagoona" in content_lower):
            if any(t in content_lower for t in BANNED_TOPICS):
                await msg.reply("That’s outside the studio’s scope 🌊 let's keep it on Roblox topics!")
                return

            async with msg.channel.typing():
                reply_text = await call_llm(msg.content)
                await asyncio.sleep(0.3)

            embed = discord.Embed(
                title="🌊 Lagoona",
                description=reply_text,
                color=discord.Color.blurple(),
            )
            embed.set_image(url=random.choice(BANNERS))

            try:
                await msg.reply(embed=embed, mention_author=False)
            except Exception as e:
                logger.warning("Embed reply failed: %s", e)

    # --- decorate Lagoona's own embeds in announcement channels ---
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author == self.bot.user and after.embeds:
            # skip if embeds unchanged
            if before.embeds == after.embeds:
                return
            for embed in after.embeds:
                embed.set_image(url=random.choice(BANNERS))
            try:
                await after.edit(embeds=after.embeds)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(SmartResponder(bot))
