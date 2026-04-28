FROM python:3.12-slim

WORKDIR /app

COPY services/issues/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/issues/app /app/app
COPY services/issues/alembic /app/alembic
COPY services/issues/alembic.ini /app/alembic.ini
COPY services/issues/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

CMD ["./entrypoint.sh"]
