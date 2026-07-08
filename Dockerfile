# Stage 1: build the React frontend
FROM node:22-slim AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime serving API + built SPA
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir ".[web]"
COPY --from=frontend /build/dist /app/webdist

ENV REFLECTOOL_DB=/data/reflectool.db \
    REFLECTOOL_STATIC=/app/webdist
VOLUME /data
EXPOSE 8000

# single worker: cycle mutations rely on in-process locking
CMD ["python", "-m", "reflectool_web"]
