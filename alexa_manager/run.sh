#!/usr/bin/with-contenv bashio

bashio::log.info "Démarrage d'Alexa Manager..."

# Récupérer le token HA superviseur
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export HA_URL="http://supervisor/core"

cd /app
python3 server.py
