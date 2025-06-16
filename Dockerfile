# Use official Python image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Ensure src and configuration folders are importable
ENV PYTHONPATH=/app/src:/app/configuration

# Install PostgreSQL client utilities and curl
RUN apt-get update && apt-get install -y postgresql-client curl

# Copy application source code
COPY src/ ./src/

# Copy scripts folder explicitly with absolute path in container
COPY src/scripts /app/scripts

# Debug: list contents of /app/scripts right after copy
RUN echo "Listing /app/scripts after copy:" && ls -la /app/scripts || echo "/app/scripts does not exist"

# Copy other necessary files to /app root
COPY requirements.txt .
COPY run.py .
COPY alembic.ini .
COPY alembic/ ./alembic/

# Set environment variable to indicate running inside Docker
ENV IN_DOCKER=true

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Debug: list contents of /app to verify all files
RUN echo "📁 Docker build: listing /app contents:" && ls -R /app

# Expose port Gunicorn will listen on
EXPOSE 8080

# On container start: run migrations, then launch Gunicorn app server
CMD alembic upgrade head && gunicorn --preload wsgi:app --bind 0.0.0.0:8080
