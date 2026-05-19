ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and aiohttp
RUN apk add --no-cache python3 py3-pip && \
    pip3 install aiohttp --break-system-packages 2>/dev/null || \
    pip3 install aiohttp

# Copy app files
COPY app/ /app/
COPY run.sh /run.sh
RUN chmod +x /run.sh

WORKDIR /app

CMD ["python3", "/app/server.py"]
