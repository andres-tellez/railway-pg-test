FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# ✅ Respect Railway's dynamic PORT
CMD ["gunicorn", "-b", "0.0.0.0:${PORT}", "wsgi:app"]
