# Utilise l'image officielle Python d'Alpine (multi-arch : amd64, arm64, armv7).
# On garde ARG BUILD_FROM pour rester compatible si Supervisor le passe quand même.
ARG BUILD_FROM=python:3.12-alpine
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

# aiohttp est notre seule dépendance
RUN pip install --no-cache-dir aiohttp==3.10.10

# Copie de l'application
COPY server.py /app/server.py
COPY index.html /app/index.html

WORKDIR /app
EXPOSE 8099

# Labels exigés par le builder HA
LABEL \
    io.hass.name="Alexa Manager" \
    io.hass.description="Gérez vos phrases vocales Alexa" \
    io.hass.type="addon" \
    io.hass.arch="aarch64|amd64|armv7"

CMD ["python3", "/app/server.py"]

