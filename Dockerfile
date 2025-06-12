# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Ensure src is importable by gunicorn
ENV PYTHONPATH=/app

# Install PostgreSQL client utilities (including pg_isready)
RUN apt-get update && apt-get install -y postgresql-client

# Copy app source and dependencies
COPY src/ ./src/
COPY requirements.txt .
COPY run.py .
COPY alembic.ini .
COPY alembic/ ./alembic/
ENV IN_DOCKER=true


# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Debug: confirm contents
RUN echo "📁 Docker build: listing /app contents:" && ls -R /app

# Expose internal container port (Gunicorn listens here)
EXPOSE 8080

# Ensure database schema is up to date by running Alembic migrations before starting the app
CMD alembic upgrade head && gunicorn --preload wsgi:app --bind 0.0.0.0:8080
