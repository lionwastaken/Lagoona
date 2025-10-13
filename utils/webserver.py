# utils/webserver.py
import os
import asyncio
from aiohttp import web
import logging
from pathlib import Path

logger = logging.getLogger("webserver")

STATIC_DIR = Path("static")

async def health_handler(request):
    return web.json_response({"status": "ok", "service": "lagoona"})

async def ping_handler(request):
    # simple ping endpoint that UptimeRobot may hit
    return web.Response(text="pong")

async def announce_receive(request):
    # Optional webhook to receive announcements from external services (social media, IFTTT, Zapier)
    try:
        data = await request.json()
    except Exception:
        data = await request.post()
    logger.info("Announcement webhook received: %s", data)
    return web.json_response({"received": True})

def start_webserver(port: int = 8080):
    app = web.Application()
    app.add_routes([
        web.get("/health", health_handler),
        web.get("/ping", ping_handler),
        web.post("/announce", announce_receive),
        # static server for images under /static/
        web.static("/static", str(STATIC_DIR.resolve()), show_index=True)
    ])
    # Ensure static dir exists
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    runner = web.AppRunner(app)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Webserver running on port {port}. Endpoints: /health /ping /announce /static/")
        while True:
            await asyncio.sleep(3600)

    loop.run_until_complete(_run())
