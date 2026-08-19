FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TYPENG_WEB_MODE=1 \
    TYPENG_HOME=/var/lib/typeng

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt \
    && useradd --create-home --uid 10001 typeng \
    && mkdir -p /var/lib/typeng/data \
    && chown -R typeng:typeng /var/lib/typeng

COPY --chown=typeng:typeng . .
RUN chmod +x /app/docker-entrypoint.sh

USER typeng
EXPOSE 8000
VOLUME ["/var/lib/typeng"]

HEALTHCHECK --interval=30s --timeout=4s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3)"

# One process owns SQLite writes; threads allow concurrent page/audio requests.
CMD ["/app/docker-entrypoint.sh"]
