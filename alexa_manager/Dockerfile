FROM python:3.11-alpine

RUN pip install aiohttp

COPY app/ /app/

WORKDIR /app

EXPOSE 8099

CMD ["python3", "server.py"]

