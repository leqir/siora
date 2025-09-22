FROM python:3.11-slim

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ruff.toml* ./
RUN uv sync

COPY app ./app

ENV PORT=8000
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
