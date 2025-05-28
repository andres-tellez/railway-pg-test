#!/bin/bash

echo "🔁 Stopping and removing containers and volumes..."
docker-compose down --volumes

echo "🔨 Rebuilding and starting containers..."
docker-compose up --build -d

echo "⏳ Waiting for PostgreSQL to accept connections..."
sleep 10

echo "📂 Verifying DB container and creating schema..."
docker-compose exec db psql -U smartcoach -d smartcoach_db -f /docker-entrypoint-initdb.d/schema.sql

echo "✅ DB schema applied. Verifying connection from app..."
docker-compose logs web | tail -n 50
