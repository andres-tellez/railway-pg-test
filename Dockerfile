# Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# ✅ This is crucial!
COPY templates/ templates/

CMD ["gunicorn", "run:app", "-b", "0.0.0.0:5050"]
