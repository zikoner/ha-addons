#!/usr/bin/env python3
"""
Alexa Manager - Serveur HTTP pour HA Ingress.

Fournit :
  - GET  /              -> sert index.html
  - GET  /health        -> diagnostic
  - GET  /api/states    -> proxy vers Supervisor REST
  - POST /api/services/<domain>/<service>  -> proxy vers Supervisor REST
  - POST /rename        -> renomme une entité via la WebSocket de HA
"""

import os
import re
import asyncio
import logging
from aiohttp import web, ClientSession, ClientTimeout, WSMsgType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s alexa-manager: %(message)s",
)
log = logging.getLogger("alexa-manager")

HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HA_URL = "http://supervisor/core"
HA_WS = "ws://supervisor/core/websocket"
PORT = 8099
APP_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(APP_DIR, "index.html")

# Regex pour strip d'éventuels préfixes Ingress résiduels
INGRESS_PREFIX_RE = re.compile(r"^/api/hassio_ingress/[^/]+(.*)")


def ha_headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


# ── Health ──────────────────────────────────────────────────────────────────

async def handle_health(request):
    return web.json_response({
        "ok": True,
        "has_token": bool(HA_TOKEN),
        "ha_url": HA_URL,
    })


# ── Proxy REST ──────────────────────────────────────────────────────────────

async def proxy_get(api_path: str):
    """Proxy un GET vers l'API REST de HA."""
    url = f"{HA_URL}/api/{api_path}"
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as s:
            async with s.get(url, headers=ha_headers()) as r:
                body = await r.read()
                return web.Response(
                    body=body,
                    status=r.status,
                    content_type="application/json",
                )
    except asyncio.TimeoutError:
        log.error("Timeout GET %s", url)
        return web.json_response({"error": "timeout"}, status=504)
    except Exception as e:
        log.error("Erreur GET %s : %s", url, e)
        return web.json_response({"error": str(e)}, status=502)


async def proxy_post(api_path: str, body: bytes):
    """Proxy un POST vers l'API REST de HA."""
    url = f"{HA_URL}/api/{api_path}"
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as s:
            async with s.post(url, headers=ha_headers(), data=body) as r:
                resp = await r.read()
                return web.Response(
                    body=resp,
                    status=r.status,
                    content_type="application/json",
                )
    except asyncio.TimeoutError:
        log.error("Timeout POST %s", url)
        return web.json_response({"error": "timeout"}, status=504)
    except Exception as e:
        log.error("Erreur POST %s : %s", url, e)
        return web.json_response({"error": str(e)}, status=502)


# ── Rename via WebSocket ────────────────────────────────────────────────────

async def rename_entity(entity_id: str, new_name: str) -> dict:
    """Renomme une entité via la WebSocket de HA.

    L'API REST de HA ne permet PAS d'écrire dans l'entity_registry — c'est
    uniquement disponible en WebSocket. On ouvre une connexion, on
    s'authentifie avec le SUPERVISOR_TOKEN, on envoie le message d'update
    et on attend la réponse correspondante.
    """
    if not HA_TOKEN:
        raise RuntimeError("SUPERVISOR_TOKEN absent — l'addon ne peut pas parler à HA")

    async with ClientSession(timeout=ClientTimeout(total=15)) as s:
        async with s.ws_connect(HA_WS, heartbeat=30) as ws:
            # 1. Réception du message auth_required
            msg = await ws.receive(timeout=10)
            if msg.type != WSMsgType.TEXT:
                raise RuntimeError(f"Message WS inattendu : {msg.type}")
            auth_req = msg.json()
            if auth_req.get("type") != "auth_required":
                raise RuntimeError(f"Handshake WS inattendu : {auth_req}")

            # 2. Envoi du token
            await ws.send_json({"type": "auth", "access_token": HA_TOKEN})
            msg = await ws.receive(timeout=10)
            auth_resp = msg.json()
            if auth_resp.get("type") != "auth_ok":
                raise RuntimeError(f"Auth WS refusée : {auth_resp}")

            # 3. Appel de config/entity_registry/update
            req_id = 1
            await ws.send_json({
                "id": req_id,
                "type": "config/entity_registry/update",
                "entity_id": entity_id,
                "name": new_name,  # None -> reset au friendly_name original
            })

            # 4. Lecture de la réponse correspondante
            while True:
                msg = await ws.receive(timeout=10)
                if msg.type == WSMsgType.CLOSED:
                    raise RuntimeError("WS fermée avant réponse")
                if msg.type != WSMsgType.TEXT:
                    continue
                data = msg.json()
                if data.get("id") != req_id:
                    continue
                if data.get("success"):
                    return data.get("result", {})
                err = data.get("error", {})
                raise RuntimeError(
                    f"HA a refusé l'update : {err.get('code')} {err.get('message')}"
                )


async def handle_rename(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "JSON invalide"}, status=400)

    entity_id = data.get("entity_id")
    new_name = data.get("name")
    if not entity_id or not isinstance(new_name, str):
        return web.json_response(
            {"error": "entity_id et name (string) sont requis"},
            status=400,
        )

    try:
        result = await rename_entity(entity_id, new_name)
        log.info("Renommé %s -> %r", entity_id, new_name)
        return web.json_response({"ok": True, "result": result})
    except Exception as e:
        log.error("rename a échoué : %s", e)
        return web.json_response({"error": str(e)}, status=500)


# ── Router unique ───────────────────────────────────────────────────────────

async def handler(request):
    # Normaliser le chemin : strip un éventuel préfixe Ingress résiduel
    path = request.path
    m = INGRESS_PREFIX_RE.match(path)
    if m:
        path = m.group(1) or "/"
    # Strip un éventuel /app/<slug> historique
    m = re.match(r"^/app/[^/]+(.*)", path)
    if m:
        path = m.group(1) or "/"

    method = request.method

    if path == "/health":
        return await handle_health(request)

    if path == "/rename" and method == "POST":
        return await handle_rename(request)

    if path.startswith("/api/"):
        api_path = path[len("/api/"):]
        if method == "POST":
            return await proxy_post(api_path, await request.read())
        if method == "GET":
            return await proxy_get(api_path)
        return web.Response(status=405)

    # Toute autre requête GET -> on sert l'UI
    if method == "GET":
        try:
            with open(HTML_PATH, "r", encoding="utf-8") as f:
                html = f.read()
            return web.Response(text=html, content_type="text/html")
        except FileNotFoundError:
            return web.Response(
                text="index.html introuvable",
                status=500,
                content_type="text/plain",
            )

    return web.Response(status=404)


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    return app


if __name__ == "__main__":
    log.info("Alexa Manager démarre sur le port %d", PORT)
    log.info("Token superviseur : %s", "OUI" if HA_TOKEN else "NON")
    log.info("Cible HA REST : %s", HA_URL)
    log.info("Cible HA WS   : %s", HA_WS)
    web.run_app(make_app(), host="0.0.0.0", port=PORT, access_log=None)
