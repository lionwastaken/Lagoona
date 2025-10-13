# Lagoona — Discord Bot (Revamped)

## Quick summary
This repo contains a production-ready Discord bot using `discord.py` (v2.x) with:
- Slash commands: /help, /ticket, /announcement, /postannouncement, and more.
- Moderation skeleton (alternate account detection, raid detection, swear/mass-ping detection).
- Uptime/health-check web server (binds to $PORT required by Render).
- Announcements that support images (attachments or static URLs).
- Ticket system (creates private ticket channels).
- Daily posting loop and "answer stale questions" loop skeletons.
- Safe LLM integration points (do not send secrets directly).

## Required environment variables (set in Render dashboard)
- `DISCORD_TOKEN` (bot token) — **Rotate immediately** if it has been exposed.
- `CLIENT_ID` (app client id)
- `OWNER_ID` (your Discord user id, optional)
- `OPENAI_API_KEY` (or GEMINI key) — use env var name you want
- `PORT` (Render sets this for you)

**Do not** commit `.env` to git.

## Deploy steps (Render)
1. Push this repo to GitHub.
2. In Render, create a new **Web Service** connected to the repo branch.
3. Set the start command to `python lagoona.py` (or use the Procfile).
4. Add environment variables in Render — `DISCORD_TOKEN`, etc.
5. Deploy. Render will use the `requirements.txt`.

## UptimeRobot
- Add a new monitor with your Render service URL `/health` to keep the bot alive.
- Optionally use the `/uptime/ping` endpoint (provided) for pings.

## Notes & security
- Rotate any tokens that were ever copied into other places.
- Use Render's environment variables to store secrets.

