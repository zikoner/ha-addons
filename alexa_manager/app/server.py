#!/usr/bin/env python3
"""
Alexa Manager - Serveur Python
Sert l'interface web et proxifie les appels API vers Home Assistant
"""

import asyncio
import json
import os
import logging
from aiohttp import web, ClientSession, ClientTimeout

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("alexa-manager")

HA_URL    = os.environ.get("HA_URL", "http://supervisor/core")
HA_TOKEN  = os.environ.get("SUPERVISOR_TOKEN", "")
PORT      = 8099
APP_DIR   = os.path.dirname(os.path.abspath(__file__))

# ── Proxy API vers HA ──────────────────────────────────────────────────────
async def proxy_get(request):
    path = request.match_info["path"]
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=10)
    async with ClientSession(timeout=timeout) as session:
        async with session.get(f"{HA_URL}/api/{path}", headers=headers) as resp:
            data = await resp.text()
            return web.Response(
                text=data,
                status=resp.status,
                content_type="application/json"
            )

async def proxy_post(request):
    path = request.match_info["path"]
    body = await request.text()
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    timeout = ClientTimeout(total=10)
    async with ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{HA_URL}/api/{path}",
            headers=headers,
            data=body
        ) as resp:
            data = await resp.text()
            return web.Response(
                text=data,
                status=resp.status,
                content_type="application/json"
            )

# ── Route principale ───────────────────────────────────────────────────────
async def index(request):
    index_path = os.path.join(APP_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(text=content, content_type="text/html")

# ── Santé ──────────────────────────────────────────────────────────────────
async def health(request):
    return web.json_response({"status": "ok", "addon": "alexa-manager"})

# ── App ────────────────────────────────────────────────────────────────────
def create_app():
    app = web.Application()
    app.router.add_get("/",               index)
    app.router.add_get("/health",         health)
    app.router.add_get("/api/{path:.+}",  proxy_get)
    app.router.add_post("/api/{path:.+}", proxy_post)
    return app

if __name__ == "__main__":
    log.info(f"Alexa Manager démarré sur le port {PORT}")
    log.info(f"HA URL: {HA_URL}")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
