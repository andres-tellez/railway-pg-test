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
COPY src/scripts /app/scripts

# Copy other necessary files to /app root
COPY requirements.txt .
COPY run.py .
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/staging_auth_app.py ./staging_auth_app.py

# Set environment variable to indicate running inside Docker
ENV IN_DOCKER=true

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose port 8080 (required by Railway)
EXPOSE 8080

# Start the staging_auth_app with gunicorn on port 8080
CMD gunicorn --bind 0.0.0.0:$PORT staging_auth_app:app
