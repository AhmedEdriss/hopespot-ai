# Dockerfile for HSO Email Agent webhook server.
#
# Build: docker build -t hso-email-agent .
# Run:   docker run -p 8080:8080 \
#          -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
#          -e HSO_WEBHOOK_SECRET=$HSO_WEBHOOK_SECRET \
#          hso-email-agent

FROM python:3.11-slim

# System hardening: minimal image, no root at runtime, no shell history.
RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the codebase. We only need agents/, shared/, kb/ at runtime.
COPY shared/ ./shared/
COPY agents/ ./agents/
COPY kb/ ./kb/

# Drop to non-root.
USER app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HSO_KB_PATH=./kb
ENV PORT=8080

EXPOSE 8080

CMD ["gunicorn", "agents.email.webhook_server:app", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "2", \
     "--timeout", "90"]
