# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Ensure src is importable by gunicorn
ENV PYTHONPATH=/app

# Copy app source and dependencies
COPY src/ ./src/
COPY requirements.txt .
COPY run.py .
COPY schema.sql /app/

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Debug: confirm contents
RUN echo "📁 Docker build: listing /app contents:" && ls -R /app

# Expose internal container port (Gunicorn listens here)
EXPOSE 8080

# Start Gunicorn with app factory
CMD ["gunicorn", "--preload", "wsgi:app", "--bind", "0.0.0.0:8080"]

