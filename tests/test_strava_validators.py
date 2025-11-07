"""
Test Strava Validation Utilities

Tests for Strava-specific input validation functions.
"""

import pytest
from flask import Flask
from src.utils.strava_validators import (
    validate_athlete_id,
    validate_activity_id,
    validate_user_id,
    validate_ingestion_params,
    validate_webhook_event,
    validate_oauth_code,
)


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestValidateAthleteId:
    """Tests for validate_athlete_id function."""

    def test_validate_athlete_id_valid_int(self, app):
        """Test validating a valid integer athlete ID."""
        with app.app_context():
            athlete_id, error = validate_athlete_id(12345)
            assert athlete_id == 12345
            assert error is None

    def test_validate_athlete_id_valid_string(self, app):
        """Test validating a valid string athlete ID."""
        with app.app_context():
            athlete_id, error = validate_athlete_id("12345")
            assert athlete_id == 12345
            assert error is None

    def test_validate_athlete_id_none(self, app):
        """Test validating None athlete ID."""
        with app.app_context():
            athlete_id, error = validate_athlete_id(None)
            assert athlete_id is None
            assert error is not None
            assert error[1] == 400
            assert "athlete_id is required" in error[0].json["error"]

    def test_validate_athlete_id_zero(self, app):
        """Test validating zero athlete ID (invalid)."""
        with app.app_context():
            athlete_id, error = validate_athlete_id(0)
            assert athlete_id is None
            assert error is not None
            assert "positive integer" in error[0].json["error"]

    def test_validate_athlete_id_negative(self, app):
        """Test validating negative athlete ID (invalid)."""
        with app.app_context():
            athlete_id, error = validate_athlete_id(-1)
            assert athlete_id is None
            assert error is not None
            assert "positive integer" in error[0].json["error"]

    def test_validate_athlete_id_too_large(self, app):
        """Test validating athlete ID that's too large."""
        with app.app_context():
            athlete_id, error = validate_athlete_id(9999999999)
            assert athlete_id is None
            assert error is not None
            assert "too large" in error[0].json["error"]

    def test_validate_athlete_id_invalid_string(self, app):
        """Test validating invalid string athlete ID."""
        with app.app_context():
            athlete_id, error = validate_athlete_id("not_a_number")
            assert athlete_id is None
            assert error is not None
            assert "valid integer" in error[0].json["error"]


class TestValidateActivityId:
    """Tests for validate_activity_id function."""

    def test_validate_activity_id_valid(self, app):
        """Test validating a valid activity ID."""
        with app.app_context():
            activity_id, error = validate_activity_id(123456789)
            assert activity_id == 123456789
            assert error is None

    def test_validate_activity_id_none(self, app):
        """Test validating None activity ID."""
        with app.app_context():
            activity_id, error = validate_activity_id(None)
            assert activity_id is None
            assert error is not None
            assert "activity_id is required" in error[0].json["error"]

    def test_validate_activity_id_zero(self, app):
        """Test validating zero activity ID (invalid)."""
        with app.app_context():
            activity_id, error = validate_activity_id(0)
            assert activity_id is None
            assert error is not None
            assert "positive integer" in error[0].json["error"]


class TestValidateUserId:
    """Tests for validate_user_id function."""

    def test_validate_user_id_valid_uuid(self, app):
        """Test validating a valid UUID."""
        with app.app_context():
            valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
            user_id, error = validate_user_id(valid_uuid)
            assert user_id == valid_uuid
            assert error is None

    def test_validate_user_id_none(self, app):
        """Test validating None user ID."""
        with app.app_context():
            user_id, error = validate_user_id(None)
            assert user_id is None
            assert error is not None
            assert "user_id is required" in error[0].json["error"]

    def test_validate_user_id_invalid_format(self, app):
        """Test validating invalid UUID format."""
        with app.app_context():
            user_id, error = validate_user_id("not-a-uuid")
            assert user_id is None
            assert error is not None
            assert "valid UUID" in error[0].json["error"]

    def test_validate_user_id_not_string(self, app):
        """Test validating non-string user ID."""
        with app.app_context():
            user_id, error = validate_user_id(12345)
            assert user_id is None
            assert error is not None
            assert "must be a string" in error[0].json["error"]


class TestValidateIngestionParams:
    """Tests for validate_ingestion_params function."""

    def test_validate_ingestion_params_all_valid(self, app):
        """Test validating all valid parameters."""
        with app.app_context():
            params, error = validate_ingestion_params(
                lookback_days=30,
                max_activities=100,
                batch_size=50,
                per_page=200,
            )
            assert error is None
            assert params["lookback_days"] == 30
            assert params["max_activities"] == 100
            assert params["batch_size"] == 50
            assert params["per_page"] == 200

    def test_validate_ingestion_params_all_none(self, app):
        """Test validating all None parameters (should be valid)."""
        with app.app_context():
            params, error = validate_ingestion_params()
            assert error is None
            assert params == {}

    def test_validate_ingestion_params_lookback_too_large(self, app):
        """Test validating lookback_days that's too large."""
        with app.app_context():
            params, error = validate_ingestion_params(lookback_days=5000)
            assert params is None
            assert error is not None
            assert "lookback_days" in error[0].json["details"]["errors"]

    def test_validate_ingestion_params_max_activities_too_large(self, app):
        """Test validating max_activities that's too large."""
        with app.app_context():
            params, error = validate_ingestion_params(max_activities=20000)
            assert params is None
            assert error is not None
            assert "max_activities" in error[0].json["details"]["errors"]

    def test_validate_ingestion_params_per_page_too_large(self, app):
        """Test validating per_page that exceeds Strava limit."""
        with app.app_context():
            params, error = validate_ingestion_params(per_page=300)
            assert params is None
            assert error is not None
            assert "per_page" in error[0].json["details"]["errors"]


class TestValidateWebhookEvent:
    """Tests for validate_webhook_event function."""

    def test_validate_webhook_event_valid_activity_create(self, app):
        """Test validating valid activity.create webhook event."""
        with app.app_context():
            event_data = {
                "object_type": "activity",
                "object_id": 123456789,
                "aspect_type": "create",
                "owner_id": 347085,
            }
            validated, error = validate_webhook_event(event_data)
            assert error is None
            assert validated == event_data

    def test_validate_webhook_event_valid_activity_update(self, app):
        """Test validating valid activity.update webhook event."""
        with app.app_context():
            event_data = {
                "object_type": "activity",
                "object_id": 123456789,
                "aspect_type": "update",
                "owner_id": 347085,
            }
            validated, error = validate_webhook_event(event_data)
            assert error is None
            assert validated == event_data

    def test_validate_webhook_event_missing_fields(self, app):
        """Test validating webhook event with missing fields."""
        with app.app_context():
            event_data = {
                "object_type": "activity",
                # Missing object_id, aspect_type, owner_id
            }
            validated, error = validate_webhook_event(event_data)
            assert validated is None
            assert error is not None
            assert "Missing required fields" in error[0].json["error"]

    def test_validate_webhook_event_invalid_object_type(self, app):
        """Test validating webhook event with invalid object_type."""
        with app.app_context():
            event_data = {
                "object_type": "invalid",
                "object_id": 123456789,
                "aspect_type": "create",
                "owner_id": 347085,
            }
            validated, error = validate_webhook_event(event_data)
            assert validated is None
            assert error is not None
            assert "object_type" in error[0].json["details"]["errors"]

    def test_validate_webhook_event_invalid_aspect_type(self, app):
        """Test validating webhook event with invalid aspect_type."""
        with app.app_context():
            event_data = {
                "object_type": "activity",
                "object_id": 123456789,
                "aspect_type": "invalid",
                "owner_id": 347085,
            }
            validated, error = validate_webhook_event(event_data)
            assert validated is None
            assert error is not None
            assert "aspect_type" in error[0].json["details"]["errors"]

    def test_validate_webhook_event_invalid_object_id(self, app):
        """Test validating webhook event with invalid object_id."""
        with app.app_context():
            event_data = {
                "object_type": "activity",
                "object_id": -1,
                "aspect_type": "create",
                "owner_id": 347085,
            }
            validated, error = validate_webhook_event(event_data)
            assert validated is None
            assert error is not None
            assert "object_id" in error[0].json["details"]["errors"]


class TestValidateOAuthCode:
    """Tests for validate_oauth_code function."""

    def test_validate_oauth_code_valid(self, app):
        """Test validating a valid OAuth code."""
        with app.app_context():
            code = "a" * 50  # Valid length
            validated, error = validate_oauth_code(code)
            assert validated == code
            assert error is None

    def test_validate_oauth_code_none(self, app):
        """Test validating None OAuth code."""
        with app.app_context():
            validated, error = validate_oauth_code(None)
            assert validated is None
            assert error is not None
            assert "OAuth code is required" in error[0].json["error"]

    def test_validate_oauth_code_too_short(self, app):
        """Test validating OAuth code that's too short."""
        with app.app_context():
            code = "short"
            validated, error = validate_oauth_code(code)
            assert validated is None
            assert error is not None
            assert "invalid length" in error[0].json["error"]

    def test_validate_oauth_code_too_long(self, app):
        """Test validating OAuth code that's too long."""
        with app.app_context():
            code = "a" * 600
            validated, error = validate_oauth_code(code)
            assert validated is None
            assert error is not None
            assert "invalid length" in error[0].json["error"]

    def test_validate_oauth_code_not_string(self, app):
        """Test validating non-string OAuth code."""
        with app.app_context():
            validated, error = validate_oauth_code(12345)
            assert validated is None
            assert error is not None
            assert "must be a string" in error[0].json["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
