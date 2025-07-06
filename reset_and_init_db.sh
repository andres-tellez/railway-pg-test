#!/bin/bash

set -e  # Exit on error
set -o pipefail

# 🛑 Safety prompt before destroying DB volume
read -p "⚠️  This will erase the DB. Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🚫 Cancelled."
    exit 1
fi

echo "🔁 Stopping and removing containers and volumes..."
docker-compose down --volumes

echo "🔨 Rebuilding and starting containers..."
docker-compose up --build -d

echo "⏳ Waiting for PostgreSQL to accept connections..."
sleep 10

echo "📂 Copying schema.sql into the DB container..."
docker cp schema.sql railway-pg-test-db-1:/tmp/schema.sql

echo "🛠 Applying schema.sql to smartcoach_db..."
docker-compose exec db psql -U smartcoach -d smartcoach_db -f /tmp/schema.sql

echo "✅ Schema applied. Tailing logs from web container..."
docker-compose logs web | tail -n 50
