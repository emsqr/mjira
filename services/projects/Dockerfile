FROM python:3.12-slim

WORKDIR /app

COPY services/projects/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/projects/app /app/app
COPY services/projects/alembic /app/alembic
COPY services/projects/alembic.ini /app/alembic.ini
COPY services/projects/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

CMD ["./entrypoint.sh"]
