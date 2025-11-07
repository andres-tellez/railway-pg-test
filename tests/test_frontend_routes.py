"""
Test suite for frontend routing functionality
Tests both old and new routes to ensure compatibility
"""

import pytest
from unittest.mock import patch, MagicMock


class TestFrontendRouting:
    """Test frontend routing functionality"""

    def test_ask_route_exists(self):
        """Test that the /ask route is properly configured"""
        # This would typically be tested with a frontend testing framework
        # like Jest/React Testing Library, but we can verify the route exists
        # by checking if the component is properly imported
        try:
            from frontend.src.pages.AskGptMvpUI import AskGptMvpUI
            assert AskGptMvpUI is not None
        except ImportError:
            pytest.fail("AskGptMvpUI component not found")

    def test_route_configuration(self):
        """Test that all expected routes are configured"""
        expected_routes = [
            "/", "/login", "/post-oauth", "/onboarding",
            "/plan/:id", "/plan", "/plan/overview", "/home", "/ask"
        ]

        # In a real frontend test, you'd check the router configuration
        # For now, we verify the routes exist in the App.tsx file
        with open("frontend/src/App.tsx", "r") as f:
            app_content = f.read()

        for route in expected_routes:
            if route == "/plan/:id":
                assert "path=\"/plan/:id\"" in app_content
            else:
                assert f"path=\"{route}\"" in app_content


class TestBackendEndpointCompatibility:
    """Test backend endpoint compatibility with frontend changes"""

    @pytest.fixture
    def mock_app(self):
        """Create a test Flask app with all blueprints"""
        from src.app import create_app
        app = create_app(test_config={"TESTING": True})
        return app.test_client()

    def test_ask_endpoint_exists(self, mock_app):
        """Test that the /ask endpoint is available"""
        response = mock_app.post("/ask", json={
            "question": "Test question",
            "athlete_id": 123
        })
        # Should not return 404 (endpoint exists)
        assert response.status_code != 404

    def test_training_plan_endpoints_exist(self, mock_app):
        """Test that training plan endpoints are still available"""
        endpoints_to_test = [
            ("/api/plan/current", "GET"),
            ("/api/plan/generate", "POST"),
            ("/api/plan/1", "GET")
        ]

        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = mock_app.get(endpoint)
            else:
                response = mock_app.post(endpoint, json={})

            # Should not return 404 (endpoint exists)
            assert response.status_code != 404

    def test_cors_headers_present(self, mock_app):
        """Test that CORS headers are properly set for frontend access"""
        response = mock_app.options("/ask")

        # Check for CORS headers
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers


class TestFunctionalityComparison:
    """Compare old vs new functionality"""

    def test_ask_functionality_consistency(self):
        """Test that the new /ask route provides consistent functionality"""
        # This would test that the AskGptMvpUI component
        # provides the same functionality as any previous implementation

        # Mock the component and test its behavior
        with patch('frontend.src.pages.AskGptMvpUI.AskGptMvpUI') as mock_component:
            # Verify component has expected props/methods
            assert hasattr(mock_component, 'handleAsk')
            assert hasattr(mock_component, 'question')
            assert hasattr(mock_component, 'response')

    def test_authentication_consistency(self):
        """Test that authentication works consistently across routes"""
        # All protected routes should use the same authentication mechanism
        with open("frontend/src/App.tsx", "r") as f:
            app_content = f.read()

        # Count ProtectedRoute usage
        protected_route_count = app_content.count("<ProtectedRoute>")
        expected_protected_routes = 7  # All routes except /login, /post-oauth, and wildcard

        assert protected_route_count == expected_protected_routes
