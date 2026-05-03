FROM python:3.12-slim

WORKDIR /app

COPY services/notifications/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/notifications/app /app/app
COPY services/notifications/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app

CMD ["./entrypoint.sh"]
