#!/usr/bin/env python3
"""
Alexa Manager - Serveur Python
Compatible Ingress Home Assistant - TESTÉ
"""

import os
import re
import logging
from aiohttp import web, ClientSession, ClientTimeout

logging.basicConfig(level=logging.INFO, format='%(levelname)s:alexa-manager:%(message)s')
log = logging.getLogger("alexa-manager")

HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HA_URL   = "http://supervisor/core"
PORT     = 8099
APP_DIR  = os.path.dirname(os.path.abspath(__file__))

def ha_headers():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

async def do_proxy_get(api_path, request):
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as s:
            async with s.get(f"{HA_URL}/api/{api_path}", headers=ha_headers()) as r:
                body = await r.read()
                return web.Response(body=body, status=r.status, content_type="application/json")
    except Exception as e:
        log.error(f"GET /api/{api_path} : {e}")
        return web.Response(text='{"error":"proxy_error"}', status=502, content_type="application/json")

async def do_proxy_post(api_path, request):
    body = await request.read()
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as s:
            async with s.post(f"{HA_URL}/api/{api_path}", headers=ha_headers(), data=body) as r:
                resp = await r.read()
                return web.Response(body=resp, status=r.status, content_type="application/json")
    except Exception as e:
        log.error(f"POST /api/{api_path} : {e}")
        return web.Response(text='{"error":"proxy_error"}', status=502, content_type="application/json")

async def router(request):
    path = request.path

    # Strip le préfixe Ingress /app/SLUG si présent
    m = re.match(r'^/app/[^/]+(.*)', path)
    if m:
        path = m.group(1) or '/'

    if path == '/health':
        return web.json_response({"ok": True, "token": bool(HA_TOKEN)})

    if path.startswith('/api/'):
        api_path = path[5:]
        if request.method == 'POST':
            return await do_proxy_post(api_path, request)
        return await do_proxy_get(api_path, request)

    # Tout le reste → page HTML
    with open(os.path.join(APP_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    return web.Response(text=html, content_type="text/html")

app = web.Application()
app.router.add_route("*", "/{tail:.*}", router)

if __name__ == "__main__":
    log.info(f"Alexa Manager démarré sur le port {PORT}")
    log.info(f"Token superviseur : {'OUI ✓' if HA_TOKEN else 'NON ✗'}")
    web.run_app(app, host="0.0.0.0", port=PORT, access_log=log)
