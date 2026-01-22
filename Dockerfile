FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY LICENSE README.md pyproject.toml /app/
COPY src /app/src

ENTRYPOINT ["python", "-m", "leximask.cli"]
