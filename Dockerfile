FROM node:20-alpine AS frontend-build

WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY backend/ /app/backend/
RUN pip install --no-cache-dir /app/backend

COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
ENV DEVFORGE_ENV=production
EXPOSE 10000

CMD ["uvicorn", "devforge.main:app", "--host", "0.0.0.0", "--port", "10000"]
