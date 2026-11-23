FROM python:3.12-alpine AS builder

RUN apk add --no-cache build-base libffi-dev
WORKDIR /build
COPY backend/requirements-prod.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-alpine

RUN addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY backend/app ./app
RUN mkdir -p /app/data && chown -R app:app /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    DATABASE_URL=sqlite:////app/data/compra_juegos.db

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
