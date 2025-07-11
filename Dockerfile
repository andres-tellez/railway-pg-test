# Base: Node for frontend, Python for backend
FROM node:18 AS frontend

# Build frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

# Python backend with Gunicorn
FROM python:3.11-slim AS backend

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Move built frontend into backend
COPY --from=frontend /app/frontend/dist ./frontend/dist

CMD ["gunicorn", "app:create_app()", "--bind", "0.0.0.0:8080", "--workers", "1"]
