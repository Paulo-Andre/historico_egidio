FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/entrypoint.sh \
    && DJANGO_SECRET_KEY=build-only-secret \
       DOCUMENT_SIGNING_KEY=build-only-signing-key \
       python manage.py collectstatic --noinput
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
