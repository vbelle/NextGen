# --- frontend build stage ---
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- backend runtime ---
# Pinned explicitly: python:3.11 is required by the LangGraph/LangChain stack.
# (Noted in plan.md: the dev sandbox this project was built in only ships 3.10
# by default, so this pin is deliberate, not incidental.)
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./backend/
RUN pip install --no-cache-dir ./backend

COPY backend/app ./backend/app
COPY --from=frontend-build /frontend/dist ./frontend/dist

ENV PYTHONPATH=/app/backend
ENV NEXTGEN_STATIC_DIR=/app/frontend/dist
ENV NEXTGEN_DB_PATH=/data/nextgen.db

VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8000"]
