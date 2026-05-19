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

logging.basicConfig(level=logging.INFO, format='%(levelname)s:alexa-manager:%(message)s')
log = logging.getLogger("alexa-manager")

# Le SUPERVISOR_TOKEN est injecté automatiquement par HA dans le conteneur
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN") or ""
HA_URL   = "http://supervisor/core"
PORT     = 8099
APP_DIR  = os.path.dirname(os.path.abspath(__file__))

def get_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }

# ── Proxy GET ──────────────────────────────────────────────────────────────
async def proxy_get(request):
    path = request.match_info["path"]
    timeout = ClientTimeout(total=10)
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{HA_URL}/api/{path}",
                headers=get_headers()
            ) as resp:
                data = await resp.text()
                return web.Response(
                    text=data,
                    status=resp.status,
                    content_type="application/json"
                )
    except Exception as e:
        log.error(f"Erreur proxy GET /{path}: {e}")
        return web.Response(
            text='{"error": "proxy error"}',
            status=500,
            content_type="application/json"
        )

# ── Proxy POST ─────────────────────────────────────────────────────────────
async def proxy_post(request):
    path = request.match_info["path"]
    body = await request.text()
    timeout = ClientTimeout(total=10)
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{HA_URL}/api/{path}",
                headers=get_headers(),
                data=body
            ) as resp:
                data = await resp.text()
                return web.Response(
                    text=data,
                    status=resp.status,
                    content_type="application/json"
                )
    except Exception as e:
        log.error(f"Erreur proxy POST /{path}: {e}")
        return web.Response(
            text='{"error": "proxy error"}',
            status=500,
            content_type="application/json"
        )

# ── Page principale ────────────────────────────────────────────────────────
async def index(request):
    index_path = os.path.join(APP_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    return web.Response(text=content, content_type="text/html")

# ── Santé ──────────────────────────────────────────────────────────────────
async def health(request):
    return web.json_response({"status": "ok", "token_present": bool(HA_TOKEN)})

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
    log.info(f"Token présent: {'OUI' if HA_TOKEN else 'NON - vérifier SUPERVISOR_TOKEN'}")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT, access_log=None)
