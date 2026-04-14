"""
Lightweight checks that core frontend routes remain declared in App.tsx.

The legacy web "Ask Coach" page at /ask has been removed; the mobile app
continues to use /api/conversations/* on the backend.
"""

import pytest


class TestFrontendRouting:
    """Verify key routes exist in frontend/src/App.tsx (source-level)."""

    def test_app_tsx_has_core_routes(self):
        with open("frontend/src/App.tsx", "r", encoding="utf-8") as f:
            app_content = f.read()

        for path in (
            "/",
            "/login",
            "/post-oauth",
            "/profile",
            "/home",
            "/plan/overview",
            "/metrics",
        ):
            assert f'path="{path}"' in app_content, f"missing route {path}"

        assert 'path="/plan/:id"' in app_content
        assert (
            'path="/ask"' not in app_content
        ), "removed web Ask Coach route must not return"


class TestBackendEndpointCompatibility:
    """Smoke checks against a test Flask app."""

    @pytest.fixture
    def mock_app(self):
        from src.app import create_app

        app = create_app(test_config={"TESTING": True})
        return app.test_client()

    def test_health_endpoint_exists(self, mock_app):
        response = mock_app.get("/health")
        assert response.status_code != 404

    def test_training_plan_endpoints_are_registered(self, mock_app):
        """Without auth, protected plan routes should not be 404 (typically 401)."""
        endpoints_to_test = [
            ("/api/plan/current", "GET"),
            ("/api/plan/draft", "POST"),
        ]

        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = mock_app.get(endpoint)
            else:
                response = mock_app.post(endpoint, json={})
            assert response.status_code != 404, f"{method} {endpoint} returned 404"

    def test_cors_headers_present(self, mock_app):
        response = mock_app.open("/health", method="OPTIONS")
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
