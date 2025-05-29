FROM ghcr.io/astral-sh/uv:python3.12-alpine

ADD . /bot
WORKDIR /bot
RUN uv sync --locked

CMD ["uv", "run", "main.py"]
