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
COPY app/staging_auth_app.py ./staging_auth_app.py

# Set environment variable to indicate running inside Docker
ENV IN_DOCKER=true

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Debug: list contents of /app to verify all files
RUN echo "📁 Docker build: listing /app contents:" && ls -R /app

# Expose the correct port (Railway uses 8080)
EXPOSE 8080

# ✅ Final entrypoint to run Flask app directly
CMD ["python", "staging_auth_app.py"]
