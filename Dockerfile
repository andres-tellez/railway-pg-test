# ─────────────────────────────
# 📦 Base Python Environment
# ─────────────────────────────
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Add src + config folders to Python path
ENV PYTHONPATH=/app/src:/app/configuration

# ─────────────────────────────
# 🔧 System Dependencies
# ─────────────────────────────
RUN apt-get update && \
    apt-get install -y postgresql-client curl && \
    apt-get clean

# ─────────────────────────────
# 🧱 Copy Application Files
# ─────────────────────────────
COPY requirements.txt .
COPY run.py .
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY app/staging_auth_app.py ./staging_auth_app.py

# ─────────────────────────────
# 🖼 Optional: Serve Vite Build
# ─────────────────────────────
COPY frontend/dist/ ./static/

# ─────────────────────────────
# 📦 Python Dependencies
# ─────────────────────────────
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ─────────────────────────────
# ⚙️ Environment + Port
# ─────────────────────────────
ENV IN_DOCKER=true
ENV PORT=8080

# Railway expects this port exposed
EXPOSE 8080

# ─────────────────────────────
# 🚀 Start Gunicorn App
# ─────────────────────────────
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "staging_auth_app:app"]
