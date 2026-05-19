ARG BUILD_FROM
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

# aiohttp est notre seule dépendance Python
RUN pip3 install --no-cache-dir --break-system-packages aiohttp==3.10.10

# Copie de l'application
COPY server.py /app/server.py
COPY index.html /app/index.html

WORKDIR /app
EXPOSE 8099

CMD ["python3", "/app/server.py"]
