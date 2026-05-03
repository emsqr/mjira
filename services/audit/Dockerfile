FROM python:3.12-slim

WORKDIR /app

COPY services/audit/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/audit/app /app/app
COPY services/audit/alembic /app/alembic
COPY services/audit/alembic.ini /app/alembic.ini
COPY services/audit/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

CMD ["./entrypoint.sh"]
