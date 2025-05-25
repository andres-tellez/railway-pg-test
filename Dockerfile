FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use shell form to expand $PORT from Railway
CMD gunicorn -b 0.0.0.0:${PORT} wsgi:app
