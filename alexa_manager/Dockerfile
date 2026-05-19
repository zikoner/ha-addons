ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN pip install --no-cache-dir aiohttp

WORKDIR /app
COPY server.py index.html /app/

EXPOSE 8099

CMD ["python3", "/app/server.py"]
