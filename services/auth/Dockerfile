FROM python:3.12-slim

WORKDIR /app

COPY services/auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/auth/app /app/app
COPY services/auth/alembic /app/alembic
COPY services/auth/alembic.ini /app/alembic.ini
COPY services/auth/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

CMD ["./entrypoint.sh"]
