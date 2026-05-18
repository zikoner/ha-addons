ARG BUILD_FROM
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache python3 py3-pip py3-aiohttp

# Copy app files
COPY run.sh /
COPY app/ /app/

RUN chmod +x /run.sh

CMD ["/run.sh"]
