#!/bin/bash

# switch_env.sh
# Usage: ./switch_env.sh [dev|test|prod]

ENV=$1

if [ -z "$ENV" ]; then
  echo "Usage: ./switch_env.sh [dev|test|prod]"
  exit 1
fi

case $ENV in
  dev)
    export FLASK_ENV=development
    echo "Switched to development (.env)"
    ;;
  test)
    export FLASK_ENV=test
    echo "Switched to test (.env.test)"
    ;;
  prod)
    export FLASK_ENV=production
    echo "Switched to production (.env.prod)"
    ;;
  *)
    echo "Invalid option: $ENV"
    echo "Usage: ./switch_env.sh [dev|test|prod]"
    exit 1
    ;;
esac

# Optional: print status
python3 -c 'import os; print(f"FLASK_ENV={os.getenv(\"FLASK_ENV\")}")'
