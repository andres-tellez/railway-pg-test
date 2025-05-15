import os, sys
# Add project root to PATH so `import src.app` works
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.app import create_app

@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
        "CRON_SECRET_KEY": "testkey",
    }
    app = create_app(test_config)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()
