FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an ordinary user, never as root.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi.py
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/api/health || exit 1

CMD exec gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --access-logfile -
