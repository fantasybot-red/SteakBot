FROM astral/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN uv sync --frozen

ENV IS_DOCKER=1

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "main.py"]
