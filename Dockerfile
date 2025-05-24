# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set PYTHONPATH to make `src` importable
ENV PYTHONPATH=/app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose port for Flask
EXPOSE 5000

# Debug test: run app with python directly to confirm it bootstraps
CMD ["python", "run.py"]
