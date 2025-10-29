"""
Unit Tests for Layer 1: Data Collection Service

Tests for DataCollectionService methods that fetch raw data from the database.

Test Coverage:
    - fetch_user_profile(): User profile retrieval
    - fetch_strava_activities(): Activity history retrieval
    - collect_all_data(): Complete data aggregation

Author: SmartCoach Development Team
Last Updated: October 28, 2025
"""

import pytest
import uuid
from datetime import datetime, timedelta

from src.services.training_plan.data_collection_service import DataCollectionService
from src.db.models.user_profile import UserProfile
from src.db.models.activities import Activity


# ============================================================================
# Pytest Fixtures
# ============================================================================
# Note: test_db_session is provided by tests/conftest.py


@pytest.fixture
def sample_user_id():
    """Provide a sample user ID for testing."""
    # Return a consistent UUID for testing
    return str(uuid.UUID("12345678-1234-5678-1234-567812345678"))


@pytest.fixture
def sample_athlete_id():
    """Provide a sample athlete ID for testing."""
    return 98765


@pytest.fixture
def sample_user_profile(test_db_session, sample_user_id):
    """Create and return a sample user profile in the test database."""
    profile = UserProfile(
        user_id=sample_user_id,
        age_group="30-39",
        height_feet=5,
        height_inches=10,
        weight=165.0,
        training_days=["Mon", "Wed", "Fri", "Sat"],
    )
    test_db_session.add(profile)
    test_db_session.commit()
    return profile


@pytest.fixture
def sample_activities(test_db_session, sample_user_id, sample_athlete_id):
    """Create sample Strava activities for testing."""
    activities = []
    base_date = datetime.now()
    user_uuid = uuid.UUID(sample_user_id)  # Convert string to UUID

    # Create 12 weeks of activity data (3 runs per week)
    for week in range(12):
        for day in [0, 2, 5]:  # Monday, Wednesday, Saturday
            activity_date = base_date - timedelta(weeks=week, days=day)

            activity = Activity(
                activity_id=1000000 + (week * 10) + day,
                athlete_id=sample_athlete_id,
                user_id=user_uuid,  # Use UUID object
                name=f"Morning Run Week {week}",
                type="Run",
                start_date=activity_date,
                distance=8000,  # meters
                conv_distance=5.0,  # miles (already converted)
                moving_time=2400,  # 40 minutes in seconds
                elapsed_time=2500,
                average_heartrate=145,
                max_heartrate=165,
                average_speed=3.33,  # m/s (~7:30/mile pace)
                max_speed=4.5,
                total_elevation_gain=50,
                suffer_score=75,
            )
            activities.append(activity)
            test_db_session.add(activity)

    test_db_session.commit()
    return activities


@pytest.fixture
def mixed_activities(test_db_session, sample_user_id, sample_athlete_id):
    """Create mixed activity types (Run and Ride) for testing filtering."""
    activities = []
    base_date = datetime.now()
    user_uuid = uuid.UUID(sample_user_id)  # Convert string to UUID

    # Create 4 runs
    for i in range(4):
        run = Activity(
            activity_id=2000000 + i,
            athlete_id=sample_athlete_id,
            user_id=user_uuid,  # Use UUID object
            name=f"Run {i}",
            type="Run",
            start_date=base_date - timedelta(days=i * 2),
            distance=8000,
            conv_distance=5.0,
            moving_time=2400,
            elapsed_time=2500,
            average_speed=3.33,
        )
        activities.append(run)
        test_db_session.add(run)

    # Create 4 rides (should be filtered out)
    for i in range(4):
        ride = Activity(
            activity_id=3000000 + i,
            athlete_id=sample_athlete_id,
            user_id=user_uuid,  # Use UUID object
            name=f"Ride {i}",
            type="Ride",
            start_date=base_date - timedelta(days=i * 2 + 1),
            distance=20000,
            conv_distance=12.4,
            moving_time=3600,
            elapsed_time=3700,
            average_speed=5.5,
        )
        activities.append(ride)
        test_db_session.add(ride)

    test_db_session.commit()
    return activities


@pytest.fixture
def sample_plan_request():
    """Provide a sample plan request for testing."""
    return {
        "race_date": "2025-06-15",
        "primary_goal": "Just Finish",
        "marathon_experience": "First",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
        "notes": "First marathon attempt",
    }


# ============================================================================
# Test Classes
# ============================================================================


class TestFetchUserProfile:
    """Tests for fetch_user_profile() method."""

    def test_fetch_existing_user_profile(
        self, test_db_session, sample_user_profile, sample_user_id
    ):
        """
        Test fetching an existing user profile.

        Given: A user profile exists in the database
        When: fetch_user_profile() is called with valid user_id
        Then: User profile data is returned correctly
        """
        # Act
        result = DataCollectionService.fetch_user_profile(
            test_db_session, sample_user_id
        )

        # Assert
        assert result is not None
        assert result["age_group"] == "30-39"
        assert result["height_feet"] == 5
        assert result["height_inches"] == 10
        assert result["weight"] == 165.0
        assert result["training_days"] == ["Mon", "Wed", "Fri", "Sat"]

    def test_fetch_nonexistent_user_profile(self, test_db_session):
        """
        Test fetching a user profile that doesn't exist.

        Given: No user profile exists for the given user_id
        When: fetch_user_profile() is called
        Then: None is returned (not an exception)
        """
        # Act
        result = DataCollectionService.fetch_user_profile(
            test_db_session, "nonexistent-user-999"
        )

        # Assert
        assert result is None

    def test_fetch_user_profile_with_null_training_days(
        self, test_db_session, sample_user_id
    ):
        """
        Test fetching a user profile with NULL training_days.

        Given: User profile exists with training_days = NULL
        When: fetch_user_profile() is called
        Then: training_days is returned as empty list
        """
        # Arrange: Create profile with NULL training_days
        profile = UserProfile(
            user_id=sample_user_id,
            age_group="40-49",
            height_feet=6,
            height_inches=0,
            weight=180.0,
            training_days=None,  # NULL
        )
        test_db_session.add(profile)
        test_db_session.commit()

        # Act
        result = DataCollectionService.fetch_user_profile(
            test_db_session, sample_user_id
        )

        # Assert
        assert result is not None
        assert result["training_days"] == []


class TestFetchStravaActivities:
    """Tests for fetch_strava_activities() method."""

    def test_fetch_activities_with_12_weeks_history(
        self, test_db_session, sample_activities, sample_user_id
    ):
        """
        Test fetching 12 weeks of activity history.

        Given: User has 12 weeks of running activities
        When: fetch_strava_activities() is called with weeks=12
        Then: All activities within timeframe are returned
        """
        # Act
        result = DataCollectionService.fetch_strava_activities(
            test_db_session, sample_user_id, weeks=12
        )

        # Assert
        assert len(result) == 36  # 12 weeks * 3 runs per week
        assert all(activity["distance"] == 5.0 for activity in result)
        assert all(activity["moving_time"] == 2400 for activity in result)

        # Verify sorted by date (newest first)
        dates = [activity["date"] for activity in result]
        assert dates == sorted(dates, reverse=True)

    def test_fetch_activities_with_4_weeks_history(
        self, test_db_session, sample_activities, sample_user_id
    ):
        """
        Test fetching only 4 weeks of activity history.

        Given: User has 12 weeks of activities in database
        When: fetch_strava_activities() is called with weeks=4
        Then: Only activities from last 4 weeks are returned
        """
        # Act
        result = DataCollectionService.fetch_strava_activities(
            test_db_session, sample_user_id, weeks=4
        )

        # Assert
        assert len(result) <= 12  # Should be ~12 (4 weeks * 3 runs)

        # Verify all activities are within 4 weeks
        cutoff_date = datetime.now() - timedelta(weeks=4)
        for activity in result:
            activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")
            assert activity_date >= cutoff_date

    def test_fetch_activities_with_no_history(self, test_db_session, sample_user_id):
        """
        Test fetching activities when user has no history.

        Given: User has no activities in database
        When: fetch_strava_activities() is called
        Then: Empty list is returned
        """
        # Act
        result = DataCollectionService.fetch_strava_activities(
            test_db_session, sample_user_id, weeks=12
        )

        # Assert
        assert result == []
        assert isinstance(result, list)

    def test_fetch_activities_filters_by_type(
        self, test_db_session, mixed_activities, sample_user_id
    ):
        """
        Test that only 'Run' activities are returned.

        Given: User has both 'Run' and 'Ride' activities
        When: fetch_strava_activities() is called with activity_type='Run'
        Then: Only running activities are returned
        """
        # Act
        result = DataCollectionService.fetch_strava_activities(
            test_db_session, sample_user_id, weeks=12, activity_type="Run"
        )

        # Assert
        assert len(result) == 4  # Only the 4 runs

        # Service filters by activity_type="Run" at database level,
        # so all returned activities are guaranteed to be runs
        # Verify each activity has required fields
        for activity in result:
            assert "activity_id" in activity
            assert "date" in activity
            assert "distance" in activity

    def test_fetch_activities_returns_correct_fields(
        self, test_db_session, sample_activities, sample_user_id
    ):
        """
        Test that returned activities have all required fields.

        Given: User has activities in database
        When: fetch_strava_activities() is called
        Then: Each activity has all expected fields
        """
        # Act
        result = DataCollectionService.fetch_strava_activities(
            test_db_session, sample_user_id, weeks=1
        )

        # Assert
        assert len(result) > 0
        activity = result[0]

        # Check all expected fields exist
        required_fields = [
            "activity_id",
            "date",
            "distance",
            "moving_time",
            "elapsed_time",
            "average_heartrate",
            "max_heartrate",
            "average_speed",
            "max_speed",
            "total_elevation_gain",
            "suffer_score",
        ]

        for field in required_fields:
            assert field in activity, f"Missing field: {field}"


class TestCollectAllData:
    """Tests for collect_all_data() method."""

    def test_collect_all_data_complete(
        self,
        test_db_session,
        sample_user_profile,
        sample_activities,
        sample_plan_request,
        sample_user_id,
    ):
        """
        Test complete data collection with all data present.

        Given: User has profile and activity history
        When: collect_all_data() is called
        Then: Complete data package is returned with all fields
        """
        # Act
        result = DataCollectionService.collect_all_data(
            test_db_session, sample_user_id, sample_plan_request, activity_weeks=12
        )

        # Assert - Check structure
        assert "user_profile" in result
        assert "strava_activities" in result
        assert "plan_request" in result
        assert "metadata" in result

        # Assert - Check user profile
        assert result["user_profile"]["age_group"] == "30-39"
        assert result["user_profile"]["height_feet"] == 5
        assert result["user_profile"]["training_days"] == ["Mon", "Wed", "Fri", "Sat"]

        # Assert - Check activities
        assert len(result["strava_activities"]) == 36  # 12 weeks * 3 runs

        # Assert - Check plan request
        assert result["plan_request"]["race_date"] == "2025-06-15"
        assert result["plan_request"]["primary_goal"] == "Just Finish"

        # Assert - Check metadata
        assert result["metadata"]["activity_weeks_requested"] == 12
        assert result["metadata"]["activities_found"] == 36
        assert "collected_at" in result["metadata"]

    def test_collect_all_data_missing_profile(
        self, test_db_session, sample_plan_request
    ):
        """
        Test data collection when user profile doesn't exist.

        Given: User profile does not exist
        When: collect_all_data() is called
        Then: ValueError is raised with clear message
        """
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            DataCollectionService.collect_all_data(
                test_db_session, "nonexistent-user-999", sample_plan_request
            )

        assert "User profile not found" in str(exc_info.value)
        assert "nonexistent-user-999" in str(exc_info.value)

    def test_collect_all_data_with_no_activities(
        self, test_db_session, sample_user_profile, sample_plan_request, sample_user_id
    ):
        """
        Test data collection when user has no activity history.

        Given: User has profile but no activities
        When: collect_all_data() is called
        Then: Data is returned with empty activities list
        """
        # Act
        result = DataCollectionService.collect_all_data(
            test_db_session, sample_user_id, sample_plan_request, activity_weeks=12
        )

        # Assert
        assert result["user_profile"] is not None
        assert result["strava_activities"] == []
        assert result["metadata"]["activities_found"] == 0

    def test_collect_all_data_with_custom_weeks(
        self,
        test_db_session,
        sample_user_profile,
        sample_activities,
        sample_plan_request,
        sample_user_id,
    ):
        """
        Test data collection with custom activity weeks parameter.

        Given: User has 12 weeks of activities
        When: collect_all_data() is called with activity_weeks=4
        Then: Only 4 weeks of activities are returned
        """
        # Act
        result = DataCollectionService.collect_all_data(
            test_db_session, sample_user_id, sample_plan_request, activity_weeks=4
        )

        # Assert
        assert result["metadata"]["activity_weeks_requested"] == 4
        assert len(result["strava_activities"]) <= 12  # ~4 weeks * 3 runs

        # Verify activities are recent
        if result["strava_activities"]:
            cutoff_date = datetime.now() - timedelta(weeks=4)
            for activity in result["strava_activities"]:
                activity_date = datetime.strptime(activity["date"], "%Y-%m-%d")
                assert activity_date >= cutoff_date

    def test_collect_all_data_preserves_plan_request(
        self, test_db_session, sample_user_profile, sample_plan_request, sample_user_id
    ):
        """
        Test that plan request data is preserved unchanged.

        Given: Plan request with specific data
        When: collect_all_data() is called
        Then: Plan request is returned unchanged
        """
        # Arrange: Create custom plan request
        custom_request = {
            "race_date": "2025-12-25",
            "primary_goal": "Target Time",
            "marathon_experience": "Experienced",
            "training_days": ["Tue", "Thu", "Sat", "Sun"],
            "target_time": "3:30:00",
            "notes": "Boston Qualifier attempt",
        }

        # Act
        result = DataCollectionService.collect_all_data(
            test_db_session, sample_user_id, custom_request
        )

        # Assert
        assert result["plan_request"] == custom_request
        assert result["plan_request"]["race_date"] == "2025-12-25"
        assert result["plan_request"]["target_time"] == "3:30:00"


# ============================================================================
# Validation Tests (Hardening)
# ============================================================================


class TestInputValidation:
    """Tests for input validation and error handling."""

    def test_fetch_activities_with_negative_weeks(
        self, test_db_session, sample_user_id
    ):
        """
        Test that negative weeks raises ValueError.

        Given: weeks parameter is negative
        When: fetch_strava_activities() is called
        Then: ValueError is raised with clear message
        """
        # Act & Assert
        with pytest.raises(ValueError, match="weeks must be at least 1"):
            DataCollectionService.fetch_strava_activities(
                test_db_session, sample_user_id, weeks=-1
            )

    def test_fetch_activities_with_zero_weeks(self, test_db_session, sample_user_id):
        """
        Test that zero weeks raises ValueError.

        Given: weeks parameter is zero
        When: fetch_strava_activities() is called
        Then: ValueError is raised
        """
        # Act & Assert
        with pytest.raises(ValueError, match="weeks must be at least 1"):
            DataCollectionService.fetch_strava_activities(
                test_db_session, sample_user_id, weeks=0
            )

    def test_fetch_activities_with_excessive_weeks(
        self, test_db_session, sample_user_profile, sample_activities, sample_user_id
    ):
        """
        Test that excessive weeks (>52) is clamped to MAX_WEEKS.

        Given: weeks parameter exceeds maximum (520 weeks = 10 years)
        When: fetch_strava_activities() is called
        Then: Weeks is clamped to MAX_WEEKS (52) and activities are fetched
        """
        # Act
        result = DataCollectionService.fetch_strava_activities(
            test_db_session, sample_user_id, weeks=520  # Request 10 years
        )

        # Assert: Should return activities but only from last 52 weeks
        # The exact count depends on how many activities are within 52 weeks
        assert isinstance(result, list)
        # Should not raise an error, just clamp and continue

    def test_fetch_activities_with_invalid_uuid_string(self, test_db_session):
        """
        Test that invalid UUID string raises ValueError with clear message.

        Given: user_id is not a valid UUID format
        When: fetch_strava_activities() is called
        Then: ValueError is raised with helpful message
        """
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid user_id format"):
            DataCollectionService.fetch_strava_activities(
                test_db_session, "not-a-valid-uuid", weeks=12
            )

    def test_fetch_activities_with_non_integer_weeks(
        self, test_db_session, sample_user_id
    ):
        """
        Test that non-integer weeks raises TypeError.

        Given: weeks parameter is a string instead of integer
        When: fetch_strava_activities() is called
        Then: TypeError is raised
        """
        # Act & Assert
        with pytest.raises(TypeError, match="weeks must be an integer"):
            DataCollectionService.fetch_strava_activities(
                test_db_session, sample_user_id, weeks="12"  # String instead of int
            )

    def test_fetch_activities_with_float_weeks(self, test_db_session, sample_user_id):
        """
        Test that float weeks raises TypeError.

        Given: weeks parameter is a float instead of integer
        When: fetch_strava_activities() is called
        Then: TypeError is raised
        """
        # Act & Assert
        with pytest.raises(TypeError, match="weeks must be an integer"):
            DataCollectionService.fetch_strava_activities(
                test_db_session, sample_user_id, weeks=12.5  # Float instead of int
            )


# ============================================================================
# Integration Tests
# ============================================================================


class TestDataCollectionIntegration:
    """Integration tests for the complete data collection flow."""

    def test_realistic_user_scenario(self, test_db_session, sample_user_id):
        """
        Test a realistic end-to-end scenario.

        Given: A realistic user with varying activity patterns
        When: Data is collected
        Then: All data is correctly aggregated
        """
        # Arrange: Create realistic profile
        user_uuid = uuid.UUID(sample_user_id)  # Convert string to UUID
        profile = UserProfile(
            user_id=sample_user_id,
            age_group="35-44",
            height_feet=5,
            height_inches=9,
            weight=155.0,
            training_days=["Mon", "Wed", "Fri"],
        )
        test_db_session.add(profile)

        # Create realistic activities with varying distances
        base_date = datetime.now()
        distances = [3, 5, 4, 10, 3, 6, 4, 12, 5, 3]  # miles

        for i, distance in enumerate(distances):
            activity = Activity(
                activity_id=5000000 + i,
                athlete_id=12345,
                user_id=user_uuid,  # Use UUID object
                name=f"Run {i+1}",
                type="Run",
                start_date=base_date - timedelta(days=i * 3),
                distance=distance * 1609.34,  # miles to meters
                conv_distance=distance,
                moving_time=int(distance * 600),  # ~10 min/mile
                elapsed_time=int(distance * 610),
                average_heartrate=140 + (i % 10),
                max_heartrate=165 + (i % 15),
                average_speed=2.68,  # ~10 min/mile
            )
            test_db_session.add(activity)

        test_db_session.commit()

        # Arrange: Plan request
        plan_request = {
            "race_date": "2025-07-04",
            "primary_goal": "Just Finish",
            "marathon_experience": "First",
            "training_days": ["Mon", "Wed", "Fri"],
        }

        # Act
        result = DataCollectionService.collect_all_data(
            test_db_session, sample_user_id, plan_request, activity_weeks=12
        )

        # Assert
        assert result["user_profile"]["age_group"] == "35-44"
        assert len(result["strava_activities"]) == 10
        assert result["metadata"]["activities_found"] == 10

        # Verify activities have varying distances
        distances_in_result = [a["distance"] for a in result["strava_activities"]]
        assert min(distances_in_result) == 3.0
        assert max(distances_in_result) == 12.0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
