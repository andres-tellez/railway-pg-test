# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set PYTHONPATH to make `src` importable
ENV PYTHONPATH=/app

# Explicit copy (avoid COPY . . which can silently fail in CI/CD)
COPY src/ ./src/
COPY requirements.txt .
COPY run.py .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Debug: list directory contents at build time
RUN echo "📁 Docker build: listing /app contents:" && ls -R /app

# TEMP: Debug import and call to create_app()
CMD ["python", "-c", "print('📦 PYTHONPATH =', __import__('os').environ.get('PYTHONPATH')); from src import app; app.create_app()"]
