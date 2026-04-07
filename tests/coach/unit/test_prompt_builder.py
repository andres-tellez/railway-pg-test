"""
Unit tests for CoachPromptBuilder.

Tests prompt building from RunnerState and QuestionContext.
"""

import pytest
from coach.prompts.prompt_builder import CoachPromptBuilder
from coach.utils.intent_classifier import Intent


class TestCoachPromptBuilder:
    """Test CoachPromptBuilder with various inputs."""

    def test_build_basic_prompt(self):
        """Test building a basic prompt with RunnerState and QuestionContext."""
        builder = CoachPromptBuilder()

        runner_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Build",
                "week_of_block": 12,
                "race": {
                    "date": "2025-06-15",
                    "distance": "Marathon",
                    "goal_type": "Target Time",
                    "target_time": "4:00:00",
                },
                "zones": {
                    "hr": {"z1": "100-110 bpm", "z2": "111-120 bpm"},
                    "pace": {"easy": "9:00-10:00/mi"},
                },
                "safety": {
                    "hr_data_reliable": True,
                    "pace_data_reliable": True,
                    "reported_injury": False,
                },
            },
        }

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": "progress_check",
            },
        }

        user_question = "How am I doing?"

        messages = builder.build(runner_state, question_context, user_question)

        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "RUNNER STATE" in messages[1]["content"]
        assert "QUESTION CONTEXT" in messages[1]["content"]
        assert user_question in messages[1]["content"]

    def test_system_prompt_includes_base_content(self):
        """Test that system prompt includes base content."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": "general_education",
            },
        }

        messages = builder.build({}, question_context, "Test question")

        system_prompt = messages[0]["content"]
        assert "expert running coach" in system_prompt.lower()
        assert "safety" in system_prompt.lower()

    def test_system_prompt_customizes_for_injury_intent(self):
        """Test that system prompt is customized for injury intent."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": Intent.INJURY_OR_SYMPTOM.value,
            },
        }

        messages = builder.build({}, question_context, "I have knee pain")

        system_prompt = messages[0]["content"]
        assert "injury" in system_prompt.lower() or "medical" in system_prompt.lower()
        assert "safety" in system_prompt.lower()

    def test_system_prompt_customizes_for_workout_review_intent(self):
        """Test that system prompt is customized for workout review intent."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": Intent.WORKOUT_REVIEW.value,
            },
        }

        messages = builder.build({}, question_context, "How did my run go?")

        system_prompt = messages[0]["content"]
        assert "workout" in system_prompt.lower() or "feedback" in system_prompt.lower()

    def test_runner_state_formatting(self):
        """Test that RunnerState is formatted correctly."""
        builder = CoachPromptBuilder()

        runner_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Peak",
                "week_of_block": 16,
                "plan_type": "Marathon_4hr",
                "race": {
                    "date": "2025-07-20",
                    "distance": "Marathon",
                    "goal_type": "Just Finish",
                },
                "zones": {
                    "hr": {"z1": "120-130 bpm"},
                    "pace": {"easy": "10:00-11:00/mi", "marathon": "9:30/mi"},
                },
                "weekly_metrics": {
                    "week_start": "2025-07-01",
                    "mileage": 45.5,
                    "volume_score": 95.0,
                    "intensity_score": 85.0,
                    "consistency_score": 90.0,
                },
                "patterns": {
                    "long_runs_too_fast_count": 2,
                    "missed_key_workouts_last_4_weeks": 1,
                    "trend": "improving",
                },
                "safety": {
                    "hr_data_reliable": True,
                    "pace_data_reliable": True,
                    "reported_injury": False,
                },
            },
        }

        question_context = {
            "version": "1.0.0",
            "question_context": {"intent": "general_education"},
        }

        messages = builder.build(runner_state, question_context, "Test")

        user_content = messages[1]["content"]
        assert "Training Phase: Peak" in user_content
        assert "Week of Block: 16" in user_content
        assert "Marathon" in user_content
        assert "45.5" in user_content  # Mileage
        assert "improving" in user_content.lower()

    def test_runner_state_formatting_includes_hr_calibration(self):
        """Test that HR calibration metadata is included when provided."""
        builder = CoachPromptBuilder()

        runner_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Build",
                "week_of_block": 8,
                "race": {"date": "2025-07-20", "distance": "Marathon"},
                "zones": {
                    "hr": {},
                    "hr_calibration": {
                        "status": "uncalibrated",
                        "reason_code": "INSUFFICIENT_DATA",
                        "qualifying_activity_count": 2,
                        "activities_needed": 3,
                        "min_activity_duration_minutes": 10,
                    },
                    "pace": {},
                },
                "safety": {
                    "hr_data_reliable": True,
                    "pace_data_reliable": True,
                    "reported_injury": False,
                },
            },
        }
        question_context = {
            "version": "1.0.0",
            "question_context": {"intent": "general_education"},
        }

        messages = builder.build(runner_state, question_context, "How am I doing?")
        user_content = messages[1]["content"]

        assert "HR Calibration" in user_content
        assert "INSUFFICIENT_DATA" in user_content
        assert "Coaching hint:" in user_content
        assert "Runs Needed: 3" in user_content

    def test_question_context_formatting_workout_review(self):
        """Test that workout review context is formatted correctly."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": Intent.WORKOUT_REVIEW.value,
                "workout_review": {
                    "activity": {
                        "date": "2025-01-15",
                        "distance_miles": 8.5,
                        "avg_pace": "9:30/mi",
                        "avg_hr": 145,
                        "zone_distribution": {"z1": "5%", "z2": "60%", "z3": "35%"},
                    },
                },
            },
        }

        messages = builder.build({}, question_context, "How did my run go?")

        user_content = messages[1]["content"]
        assert "Workout Review Context" in user_content
        assert "8.5" in user_content  # Distance
        assert "145" in user_content  # HR
        assert "Z2" in user_content  # Zone distribution

    def test_question_context_formatting_this_week_plan(self):
        """Test that this week plan context is formatted correctly."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": Intent.THIS_WEEK_PLAN.value,
                "this_week_plan": {
                    "current_week": {
                        "week_number": 12,
                        "workouts": [
                            {
                                "day": "Monday",
                                "type": "Easy Run",
                                "miles": 5.0,
                                "pace": "9:00-10:00/mi",
                            },
                            {
                                "day": "Wednesday",
                                "type": "Tempo Run",
                                "miles": 6.0,
                                "pace": "8:00/mi",
                            },
                        ],
                    },
                },
            },
        }

        messages = builder.build({}, question_context, "What's my plan this week?")

        user_content = messages[1]["content"]
        assert "This Week Plan" in user_content
        assert "Week Number: 12" in user_content
        assert "Monday" in user_content
        assert "Easy Run" in user_content

    def test_question_context_formatting_progress_check(self):
        """Test that progress check context is formatted correctly."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": Intent.PROGRESS_CHECK.value,
                "progress_check": {
                    "last_7_days_summary": {
                        "total_miles": 32.5,
                        "activity_count": 5,
                        "average_pace_seconds_per_mile": 600.0,  # 10:00/mi
                        "average_heartrate": 140,
                    },
                },
            },
        }

        messages = builder.build({}, question_context, "How am I doing?")

        user_content = messages[1]["content"]
        assert "Progress Check Context" in user_content
        assert "32.5" in user_content  # Total miles
        assert "5" in user_content  # Activity count
        assert "140" in user_content  # Average HR

    def test_question_context_formatting_injury(self):
        """Test that injury context includes safety flags."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {
                "intent": Intent.INJURY_OR_SYMPTOM.value,
                "injury_or_symptom": {
                    "safety_flags": ["chest pain", "dizziness"],
                },
            },
        }

        messages = builder.build({}, question_context, "I have chest pain")

        user_content = messages[1]["content"]
        assert "Injury/Symptom Context" in user_content
        assert "chest pain" in user_content.lower()

    def test_conversation_history_included(self):
        """Test that conversation history is included when provided."""
        builder = CoachPromptBuilder()

        runner_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Build",
                "week_of_block": 10,
                "race": {"date": "2025-06-15", "distance": "Marathon"},
                "zones": {"hr": {}, "pace": {}},
                "safety": {
                    "hr_data_reliable": True,
                    "pace_data_reliable": True,
                    "reported_injury": False,
                },
            },
        }

        question_context = {
            "version": "1.0.0",
            "question_context": {"intent": "general_education"},
        }

        conversation_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]

        messages = builder.build(
            runner_state,
            question_context,
            "Current question",
            conversation_history=conversation_history,
        )

        # Should have: system, user (with context), previous messages, current question
        assert len(messages) >= 4
        assert messages[-2]["content"] == "Previous answer"
        assert messages[-1]["content"] == "Current question"

    def test_conversation_history_limited(self):
        """Test that conversation history is limited to last 10 messages."""
        builder = CoachPromptBuilder()

        conversation_history = [
            {"role": "user", "content": f"Question {i}"}
            for i in range(15)  # 15 messages
        ]

        messages = builder.build(
            {},
            {"version": "1.0.0", "question_context": {"intent": "general_education"}},
            "Current",
            conversation_history,
        )

        # Should have: system, user (with context), last 10 history, current
        # Max should be ~13 messages (system + context user + 10 history + current)
        assert len(messages) <= 13

    def test_handles_missing_runner_state(self):
        """Test that builder handles missing RunnerState gracefully."""
        builder = CoachPromptBuilder()

        question_context = {
            "version": "1.0.0",
            "question_context": {"intent": "general_education"},
        }

        messages = builder.build({}, question_context, "Test question")

        # Should still build valid prompt
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_handles_missing_question_context(self):
        """Test that builder handles missing QuestionContext gracefully."""
        builder = CoachPromptBuilder()

        runner_state = {
            "version": "1.0.0",
            "runner_state": {
                "phase": "Build",
                "week_of_block": 10,
                "race": {"date": "2025-06-15", "distance": "Marathon"},
                "zones": {"hr": {}, "pace": {}},
                "safety": {
                    "hr_data_reliable": True,
                    "pace_data_reliable": True,
                    "reported_injury": False,
                },
            },
        }

        messages = builder.build(runner_state, {}, "Test question")

        # Should still build valid prompt
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"

    def test_error_handling_returns_fallback(self):
        """Test that errors return a fallback prompt."""
        builder = CoachPromptBuilder()

        # Force an error by passing invalid data
        # Builder should handle gracefully
        messages = builder.build(None, None, "Test question")

        # Should return minimal fallback prompt
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Test question" in messages[1]["content"]
