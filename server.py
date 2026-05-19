#!/usr/bin/env python3
"""
Alexa Manager - Serveur Python
Compatible Ingress Home Assistant
"""

import os
import re
import json
import logging
from aiohttp import web, ClientSession, ClientTimeout, WSMsgType

logging.basicConfig(level=logging.INFO, format='%(levelname)s:alexa-manager:%(message)s')
log = logging.getLogger("alexa-manager")

HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HA_URL   = "http://supervisor/core"
HA_WS    = "ws://supervisor/core/websocket"
PORT     = 8099
APP_DIR  = os.path.dirname(os.path.abspath(__file__))


def ha_headers():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}


# ── Proxy REST (GET / POST) ─────────────────────────────────────────────────

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


# ── Rename via WebSocket ────────────────────────────────────────────────────

async def rename_entity(entity_id: str, new_name: str):
    """Modifie le friendly_name d'une entité via l'API WebSocket de HA."""
    msg_id = 1
    async with ClientSession() as s:
        async with s.ws_connect(HA_WS, heartbeat=30) as ws:
            # 1) attendre le auth_required
            first = await ws.receive_json(timeout=10)
            if first.get("type") != "auth_required":
                raise RuntimeError(f"Réponse WS inattendue : {first}")

            # 2) envoyer l'auth
            await ws.send_json({"type": "auth", "access_token": HA_TOKEN})
            auth_resp = await ws.receive_json(timeout=10)
            if auth_resp.get("type") != "auth_ok":
                raise RuntimeError(f"Auth WS refusée : {auth_resp}")

            # 3) appeler config/entity_registry/update
            await ws.send_json({
                "id": msg_id,
                "type": "config/entity_registry/update",
                "entity_id": entity_id,
                "name": new_name,   # name = override utilisateur, pas friendly_name
            })

            # 4) lire la réponse correspondante
            while True:
                resp = await ws.receive_json(timeout=10)
                if resp.get("id") == msg_id:
                    if resp.get("success"):
                        return resp.get("result")
                    raise RuntimeError(f"HA a rejeté : {resp.get('error')}")


async def handle_rename(request):
    try:
        data = await request.json()
        entity_id = data.get("entity_id")
        new_name  = data.get("name")
        if not entity_id or new_name is None:
            return web.json_response({"error": "entity_id et name requis"}, status=400)
        result = await rename_entity(entity_id, new_name)
        return web.json_response({"ok": True, "result": result})
    except Exception as e:
        log.exception(f"rename a échoué : {e}")
        return web.json_response({"error": str(e)}, status=500)


# ── Router ──────────────────────────────────────────────────────────────────

async def router(request):
    path = request.path

    # Strip le préfixe Ingress /app/SLUG si présent
    m = re.match(r'^/app/[^/]+(.*)', path)
    if m:
        path = m.group(1) or '/'

    if path == '/health':
        return web.json_response({"ok": True, "token": bool(HA_TOKEN)})

    # Endpoint custom pour renommer (utilise WS côté serveur)
    if path == '/rename' and request.method == 'POST':
        return await handle_rename(request)

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
