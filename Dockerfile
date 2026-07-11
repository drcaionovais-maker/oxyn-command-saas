FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY scripts ./scripts
EXPOSE 8000
CMD ["sh", "-c", "python -m scripts.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
