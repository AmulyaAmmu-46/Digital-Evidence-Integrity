FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000

RUN addgroup --system --gid 10001 appgroup \
    && adduser --system --uid 10001 --ingroup appgroup appgroup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads data && chown -R appgroup:appgroup /app

USER appgroup

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import os; from urllib.request import urlopen; urlopen(f\"http://127.0.0.1:{os.getenv('PORT', '5000')}/health\", timeout=2)"]

CMD ["sh", "-c", "exec gunicorn --bind \"${HOST:-0.0.0.0}:${PORT:-5000}\" --workers 3 run:app"]
