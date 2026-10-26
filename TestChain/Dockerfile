FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home testchain
COPY --chown=testchain:testchain . .
RUN mkdir -p staticfiles && chown testchain:testchain staticfiles
USER testchain
RUN DEBUG=true python manage.py collectstatic --noinput && rm -f .local-secret
EXPOSE 8000
CMD ["sh", "docker-entrypoint.sh"]
