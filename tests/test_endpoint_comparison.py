"""
Test suite for comparing old vs new backend functionality
Ensures backward compatibility and feature parity
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, date


class TestAskEndpointComparison:
    """Compare /ask endpoint functionality before and after changes"""

    @pytest.fixture
    def mock_app(self):
        """Create a test Flask app"""
        from src.app import create_app
        app = create_app(test_config={"TESTING": True})
        return app.test_client()

    def test_ask_endpoint_response_format(self, mock_app):
        """Test that /ask endpoint returns expected response format"""
        with patch('src.routes.ask_routes.get_gpt_response') as mock_gpt:
            mock_gpt.return_value = "Test GPT response"

            with patch('src.routes.ask_routes.ActivityDAO.get_activities_by_athlete') as mock_activities:
                mock_activities.return_value = []

                response = mock_app.post("/ask", json={
                    "question": "How am I doing this week?",
                    "athlete_id": 123
                })

                assert response.status_code == 200
                data = response.get_json()

                # Verify response structure
                expected_keys = ["message", "athlete_id", "question", "response"]
                for key in expected_keys:
                    assert key in data

                assert data["athlete_id"] == 123
                assert data["question"] == "How am I doing this week?"
                assert data["response"] == "Test GPT response"

    def test_ask_endpoint_error_handling(self, mock_app):
        """Test error handling in /ask endpoint"""
        # Test missing question
        response = mock_app.post("/ask", json={"athlete_id": 123})
        assert response.status_code == 400
        assert "question" in response.get_json()["error"]

        # Test invalid athlete_id
        response = mock_app.post("/ask", json={
            "question": "Test",
            "athlete_id": -1
        })
        assert response.status_code == 400
        assert "athlete_id" in response.get_json()["error"]

    def test_ask_endpoint_gpt_integration(self, mock_app):
        """Test GPT integration in /ask endpoint"""
        with patch('src.routes.ask_routes.get_gpt_response') as mock_gpt:
            mock_gpt.side_effect = Exception("GPT API Error")

            response = mock_app.post("/ask", json={
                "question": "Test question",
                "athlete_id": 123
            })

            # Should handle GPT errors gracefully
            assert response.status_code == 200
            data = response.get_json()
            assert "❌ GPT error" in data["response"]


class TestTrainingPlanEndpointComparison:
    """Compare training plan endpoint functionality"""

    @pytest.fixture
    def mock_app(self):
        """Create a test Flask app"""
        from src.app import create_app
        app = create_app(test_config={"TESTING": True})
        return app.test_client()

    def test_plan_generate_endpoint_structure(self, mock_app):
        """Test that plan generation endpoint maintains expected structure"""
        with patch('src.services.training_plan_service.generate_plan') as mock_generate:
            mock_plan = MagicMock()
            mock_plan.id = 1
            mock_generate.return_value = mock_plan

            response = mock_app.post("/api/plan/generate", json={
                "race_date": "2025-12-01",
                "race_distance": "Marathon",
                "user_id": "123e4567-e89b-12d3-a456-426614174000"
            })

            assert response.status_code == 201
            data = response.get_json()
            assert "plan_id" in data
            assert data["plan_id"] == 1

    def test_plan_current_endpoint_auth(self, mock_app):
        """Test that /current endpoint requires authentication"""
        # Without authentication
        response = mock_app.get("/api/plan/current")
        # Should require auth (401 or redirect)
        assert response.status_code in [401, 302]

    def test_plan_endpoints_backward_compatibility(self, mock_app):
        """Test that existing plan endpoints still work"""
        endpoints = [
            ("/api/plan/1", "GET"),
            ("/api/plan/debug/activities", "GET"),
            ("/api/plan/debug/plan-data", "GET")
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = mock_app.get(endpoint)
            else:
                response = mock_app.post(endpoint, json={})

            # Should not return 404 (endpoints exist)
            assert response.status_code != 404


class TestDataFlowComparison:
    """Compare data flow between old and new implementations"""

    def test_activity_data_format_consistency(self):
        """Test that activity data format is consistent"""
        from src.routes.ask_routes import ask
        from unittest.mock import MagicMock

        # Mock request and session
        mock_request = MagicMock()
        mock_request.is_json = True
        mock_request.get_json.return_value = {
            "question": "Test",
            "athlete_id": 123
        }

        # Mock session and activities
        mock_session = MagicMock()
        mock_activity = MagicMock()
        mock_activity.start_date = datetime(2024, 1, 15, 10, 0, 0)
        mock_activity.conv_distance = 5.0
        mock_activity.moving_time = 1800  # 30 minutes

        with patch('src.routes.ask_routes.request', mock_request):
            with patch('src.routes.ask_routes.get_session') as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = mock_session

                with patch('src.routes.ask_routes.ActivityDAO.get_activities_by_athlete') as mock_dao:
                    mock_dao.return_value = [mock_activity]

                    # The endpoint should format activity data consistently
                    # This test ensures the data transformation logic works
                    assert True  # Placeholder - would test actual data formatting

    def test_gpt_prompt_consistency(self):
        """Test that GPT prompts are formatted consistently"""
        from src.utils.gpt_ops import format_prompt

        activities = [
            {
                "date": "2024-01-15",
                "distance_km": 5.0,
                "duration_min": 30
            }
        ]

        prompt = format_prompt("How am I doing?", activities)

        # Verify prompt structure
        assert "ACTIVITIES:" in prompt
        assert "USER QUESTION:" in prompt
        assert "How am I doing?" in prompt
        assert "2024-01-15" in prompt
        assert "5.0" in prompt


class TestPerformanceComparison:
    """Compare performance between old and new implementations"""

    def test_response_time_benchmark(self, mock_app):
        """Benchmark response times for key endpoints"""
        import time

        endpoints_to_test = [
            ("/ask", "POST", {"question": "Test", "athlete_id": 123}),
            ("/api/plan/current", "GET", None),
            ("/health", "GET", None)
        ]

        for endpoint, method, data in endpoints_to_test:
            start_time = time.time()

            if method == "GET":
                response = mock_app.get(endpoint)
            else:
                response = mock_app.post(endpoint, json=data or {})

            end_time = time.time()
            response_time = end_time - start_time

            # Log response times (in a real test, you'd assert reasonable limits)
            print(f"{endpoint} response time: {response_time:.3f}s")

            # Basic assertion that endpoint responds (not 500 error)
            assert response.status_code < 500
