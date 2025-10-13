# Lagoona — Discord Bot (Revamped)

## Quick summary
This repo contains a production-ready Discord bot using `discord.py` (v2.x) with:
- Slash commands: /help, /ticket, /announcement, /postannouncement, and more.
- Moderation skeleton (alternate account detection, raid detection, swear/mass-ping detection).
- Uptime/health-check web server (binds to $PORT required by Render).
- Announcements that support images (attachments or static URLs).
- Ticket system (creates private ticket channels).
- Daily posting loop and "answer stale questions" loop skeletons.
- Safe LLM integration points.
