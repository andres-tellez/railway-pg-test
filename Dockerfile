# Use an official Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (node + build tools)
RUN apt-get update && apt-get install -y curl gnupg build-essential

# Install Node.js (for building frontend)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# ─────────────────────────────
# 1. Build frontend
# ─────────────────────────────
COPY frontend ./frontend
RUN cd frontend && npm install && npm run build

# ─────────────────────────────
# 2. Copy backend code
# ─────────────────────────────
COPY . .

# ─────────────────────────────
# 3. Install backend dependencies
# ─────────────────────────────
RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────
# 4. Expose port and define ENV
# ─────────────────────────────
ENV FLASK_ENV=production
ENV PORT=8080

# ─────────────────────────────
# 5. Run app using Gunicorn
# ─────────────────────────────
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run:app"]
