"""
Tests for ActivitySummarizer.

Tests verify that activities are correctly summarized into compact,
GPT-friendly formats with key metrics and patterns extracted.
"""

import pytest
from datetime import date, timedelta
from coach.builders.activity_summarizer import ActivitySummarizer, ActivitySummary


class TestActivitySummarizerBasic:
    """Test basic summarization functionality."""

    def test_summarize_empty_activities(self):
        """Test summarizing empty activity list."""
        summarizer = ActivitySummarizer()

        summary = summarizer.summarize([])

        assert summary.last_7_days_summary is not None
        assert summary.last_7_days_summary.total_miles == 0.0
        assert summary.last_7_days_summary.activity_count == 0
        assert summary.last_3_long_runs == []
        assert summary.weekly_aggregates == []

    def test_summarize_single_activity(self):
        """Test summarizing a single activity."""
        summarizer = ActivitySummarizer()

        activity = {
            "date": date.today().isoformat(),
            "distance_miles": 5.0,
            "pace_seconds_per_mile": 600,  # 10:00/mile
            "average_heartrate": 150,
            "workout_type": "easy",
        }

        summary = summarizer.summarize([activity])

        assert summary.last_7_days_summary.total_miles == 5.0
        assert summary.last_7_days_summary.activity_count == 1
        assert len(summary.last_3_long_runs) == 0  # 5 miles is not a long run

    def test_summarize_multiple_activities(self):
        """Test summarizing multiple activities."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": (date.today() - timedelta(days=1)).isoformat(),
                "distance_miles": 3.0,
                "pace_seconds_per_mile": 540,  # 9:00/mile
                "average_heartrate": 160,
                "workout_type": "tempo",
            },
            {
                "date": (date.today() - timedelta(days=2)).isoformat(),
                "distance_miles": 6.0,
                "pace_seconds_per_mile": 600,  # 10:00/mile
                "average_heartrate": 140,
                "workout_type": "easy",
            },
        ]

        summary = summarizer.summarize(activities)

        assert summary.last_7_days_summary.total_miles == 9.0
        assert summary.last_7_days_summary.activity_count == 2


class TestActivitySummarizerLongRuns:
    """Test long run extraction."""

    def test_extract_long_runs(self):
        """Test extracting last 3 long runs."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": (date.today() - timedelta(days=1)).isoformat(),
                "distance_miles": 10.0,  # Long run
                "pace_seconds_per_mile": 600,
                "average_heartrate": 145,
                "workout_type": "long run",
            },
            {
                "date": (date.today() - timedelta(days=3)).isoformat(),
                "distance_miles": 12.0,  # Long run
                "pace_seconds_per_mile": 610,
                "average_heartrate": 148,
                "workout_type": "long run",
            },
            {
                "date": (date.today() - timedelta(days=5)).isoformat(),
                "distance_miles": 15.0,  # Long run
                "pace_seconds_per_mile": 590,
                "average_heartrate": 150,
                "workout_type": "long run",
            },
            {
                "date": (date.today() - timedelta(days=7)).isoformat(),
                "distance_miles": 8.0,  # Should be included if we need 3
                "pace_seconds_per_mile": 620,
                "average_heartrate": 142,
                "workout_type": "long run",
            },
        ]

        summary = summarizer.summarize(activities)

        # Should get last 3 long runs (most recent first)
        assert len(summary.last_3_long_runs) == 3
        assert summary.last_3_long_runs[0]["distance_miles"] == 10.0  # Most recent
        assert summary.last_3_long_runs[1]["distance_miles"] == 12.0
        assert summary.last_3_long_runs[2]["distance_miles"] == 15.0

    def test_long_run_threshold(self):
        """Test that long runs are identified by distance threshold."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": date.today().isoformat(),
                "distance_miles": 8.0,  # Exactly at threshold, but not marked as long run
                "pace_seconds_per_mile": 600,
                "workout_type": "easy",
            },
            {
                "date": (date.today() - timedelta(days=1)).isoformat(),
                "distance_miles": 10.0,  # Over threshold (> 8.0)
                "pace_seconds_per_mile": 600,
                "workout_type": "easy",
            },
        ]

        summary = summarizer.summarize(activities)

        # 8.0 is exactly at threshold but not explicitly marked as long run, so shouldn't be included
        # Only 10.0 should be included (distance > 8.0)
        assert len(summary.last_3_long_runs) == 1
        assert summary.last_3_long_runs[0]["distance_miles"] == 10.0


class TestActivitySummarizerWeeklyAggregates:
    """Test weekly aggregate calculations."""

    def test_weekly_aggregates_calculation(self):
        """Test that weekly aggregates are calculated correctly."""
        summarizer = ActivitySummarizer()

        # Create activities spanning 2 weeks
        today = date.today()
        activities = [
            {
                "date": (today - timedelta(days=1)).isoformat(),  # This week
                "distance_miles": 5.0,
                "pace_seconds_per_mile": 600,
                "workout_type": "easy",
            },
            {
                "date": (today - timedelta(days=2)).isoformat(),  # This week
                "distance_miles": 3.0,
                "pace_seconds_per_mile": 540,
                "workout_type": "tempo",
            },
            {
                "date": (today - timedelta(days=8)).isoformat(),  # Last week
                "distance_miles": 6.0,
                "pace_seconds_per_mile": 600,
                "workout_type": "easy",
            },
        ]

        summary = summarizer.summarize(activities)

        # Should have weekly aggregates
        assert len(summary.weekly_aggregates) >= 1
        # Most recent week should have 8.0 miles (5 + 3)
        most_recent_week = summary.weekly_aggregates[0]
        assert most_recent_week.total_miles == 8.0
        assert most_recent_week.activity_count == 2


class TestActivitySummarizerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_missing_fields(self):
        """Test handling of activities with missing fields."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": date.today().isoformat(),
                "distance_miles": 5.0,
                # Missing pace, HR, workout_type
            },
        ]

        summary = summarizer.summarize(activities)

        # Should handle gracefully without errors
        assert summary.last_7_days_summary.total_miles == 5.0
        assert summary.last_7_days_summary.activity_count == 1

    def test_future_dates(self):
        """Test that future-dated activities are handled."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),  # Future
                "distance_miles": 5.0,
                "pace_seconds_per_mile": 600,
            },
        ]

        summary = summarizer.summarize(activities)

        # Should handle gracefully (may exclude or include based on logic)
        # The important thing is it doesn't crash
        assert summary is not None

    def test_very_old_activities(self):
        """Test handling of very old activities."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": (date.today() - timedelta(days=365)).isoformat(),  # 1 year ago
                "distance_miles": 10.0,
                "pace_seconds_per_mile": 600,
            },
        ]

        summary = summarizer.summarize(activities)

        # Should handle gracefully
        assert summary is not None
        # Very old activities might be excluded from last_7_days_summary
        # but shouldn't cause errors

    def test_large_activity_list(self):
        """Test handling of large activity lists."""
        summarizer = ActivitySummarizer()

        # Generate 100 activities
        activities = []
        for i in range(100):
            activities.append(
                {
                    "date": (date.today() - timedelta(days=i)).isoformat(),
                    "distance_miles": 5.0 + (i % 10),
                    "pace_seconds_per_mile": 600,
                    "workout_type": "easy",
                }
            )

        summary = summarizer.summarize(activities)

        # Should handle large lists efficiently
        assert summary is not None
        # Should still only return last 3 long runs (not all 100)
        assert len(summary.last_3_long_runs) <= 3


class TestActivitySummarizerFormat:
    """Test output format and structure."""

    def test_summary_structure(self):
        """Test that summary has correct structure."""
        summarizer = ActivitySummarizer()

        activities = [
            {
                "date": date.today().isoformat(),
                "distance_miles": 5.0,
                "pace_seconds_per_mile": 600,
                "average_heartrate": 150,
                "workout_type": "easy",
            },
        ]

        summary = summarizer.summarize(activities)

        # Verify structure
        assert hasattr(summary, "last_7_days_summary")
        assert hasattr(summary, "last_3_long_runs")
        assert hasattr(summary, "weekly_aggregates")

        # Verify last_7_days_summary structure
        last_7 = summary.last_7_days_summary
        assert hasattr(last_7, "total_miles")
        assert hasattr(last_7, "activity_count")
        assert isinstance(last_7.total_miles, (int, float))
        assert isinstance(last_7.activity_count, int)

        # Verify last_3_long_runs is a list
        assert isinstance(summary.last_3_long_runs, list)

        # Verify weekly_aggregates is a list
        assert isinstance(summary.weekly_aggregates, list)
