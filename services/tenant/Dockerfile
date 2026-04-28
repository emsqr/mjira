FROM python:3.12-slim

WORKDIR /app

COPY services/tenant/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/tenant/app /app/app
COPY services/tenant/alembic /app/alembic
COPY services/tenant/alembic.ini /app/alembic.ini
COPY services/tenant/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

CMD ["./entrypoint.sh"]
