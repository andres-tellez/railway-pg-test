#!/usr/bin/env python3
"""
Comprehensive GPT Test Suite for Running Coach
Tests all possible question types and validates responses against database data
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import re
import json
from datetime import datetime, timedelta

# Load environment variables first
load_dotenv(".env.local")

# Add project root to path
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

from src.services.streamlined_conversation_service import StreamlinedConversationService
from src.utils.gpt_ops import get_conversation_response
from src.routes.conversation_routes import build_gpt_messages
from src.db.db_session import get_session
from sqlalchemy import text


class GPTTestSuite:
    def __init__(self):
        self.session = get_session()
        self.user_id = self._get_user_id()
        self.service = StreamlinedConversationService(self.user_id)
        self.test_results = []

    def _get_user_id(self):
        """Get a real user_id from database"""
        result = self.session.execute(
            text("SELECT user_id FROM user_profile LIMIT 1")
        ).fetchone()
        if not result:
            raise Exception("No users found in database")
        return result[0]

    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("=" * 80)
        print("COMPREHENSIVE GPT TEST SUITE")
        print("=" * 80)

        # Test categories
        self.test_plan_analysis_questions()
        self.test_progress_tracking_questions()
        self.test_historical_analysis_questions()
        self.test_future_planning_questions()
        self.test_mixed_questions()
        self.test_calculation_accuracy()
        self.test_data_source_distinction()

        # Generate report
        self.generate_test_report()

    def test_plan_analysis_questions(self):
        """Test questions about training plan analysis"""
        print("\n" + "=" * 60)
        print("TESTING PLAN ANALYSIS QUESTIONS")
        print("=" * 60)

        questions = [
            "How does my training plan look?",
            "What's my weekly mileage progression?",
            "How many long runs do I have planned?",
            "What's the structure of my training plan?",
            "How does my plan prepare me for the marathon?",
            "What's my total planned mileage?",
            "How many weeks until my race?",
            "What's my peak week mileage?",
        ]

        for question in questions:
            self._test_question(question, "plan_analysis")

    def test_progress_tracking_questions(self):
        """Test questions about training progress"""
        print("\n" + "=" * 60)
        print("TESTING PROGRESS TRACKING QUESTIONS")
        print("=" * 60)

        questions = [
            "How am I doing with my training?",
            "What runs have I completed this month?",
            "How is my training progressing?",
            "Am I on track with my plan?",
            "What's my recent training volume?",
            "How many runs have I done this week?",
            "What's my current fitness level?",
            "How consistent have I been?",
        ]

        for question in questions:
            self._test_question(question, "progress_tracking")

    def test_historical_analysis_questions(self):
        """Test questions about historical data"""
        print("\n" + "=" * 60)
        print("TESTING HISTORICAL ANALYSIS QUESTIONS")
        print("=" * 60)

        questions = [
            "What were my best runs last month?",
            "How did I perform in October?",
            "What was my longest run this year?",
            "What's my average pace recently?",
            "How has my heart rate been?",
            "What was my best week of training?",
            "How many miles did I run last month?",
            "What's my training history?",
        ]

        for question in questions:
            self._test_question(question, "historical_analysis")

    def test_future_planning_questions(self):
        """Test questions about future planning"""
        print("\n" + "=" * 60)
        print("TESTING FUTURE PLANNING QUESTIONS")
        print("=" * 60)

        questions = [
            "What should I run next week?",
            "What's coming up in my training?",
            "What's my next long run?",
            "How should I prepare for my race?",
            "What's my training schedule for December?",
            "What workouts are planned for next month?",
            "How should I taper for my race?",
            "What's my race week plan?",
        ]

        for question in questions:
            self._test_question(question, "future_planning")

    def test_mixed_questions(self):
        """Test questions that mix planned and actual data"""
        print("\n" + "=" * 60)
        print("TESTING MIXED QUESTIONS")
        print("=" * 60)

        questions = [
            "Compare my plan to what I've actually done",
            "How does my actual training compare to my plan?",
            "Am I following my training plan correctly?",
            "What's the difference between my planned and actual runs?",
            "How well am I executing my plan?",
            "What adjustments should I make to my plan?",
            "How does my progress match my expectations?",
            "What's working and what's not in my training?",
        ]

        for question in questions:
            self._test_question(question, "mixed")

    def test_calculation_accuracy(self):
        """Test specific calculations for accuracy"""
        print("\n" + "=" * 60)
        print("TESTING CALCULATION ACCURACY")
        print("=" * 60)

        # Test specific week calculations
        test_weeks = [
            ("2025-10-27", "2025-11-02", "October 27 week"),
            ("2025-11-03", "2025-11-09", "November 3 week"),
            ("2025-12-01", "2025-12-07", "December 1 week"),
        ]

        for start_date, end_date, week_name in test_weeks:
            question = f"What's my total planned mileage for the week of {start_date}?"
            self._test_question(
                question,
                "calculation",
                extra_data={
                    "start_date": start_date,
                    "end_date": end_date,
                    "week_name": week_name,
                },
            )

    def test_data_source_distinction(self):
        """Test if GPT can distinguish between planned and actual data"""
        print("\n" + "=" * 60)
        print("TESTING DATA SOURCE DISTINCTION")
        print("=" * 60)

        questions = [
            "What runs do I have planned for next week?",
            "What runs did I complete last week?",
            "What's the difference between my planned and actual runs?",
            "How many planned runs do I have vs completed runs?",
            "What's my planned mileage vs actual mileage?",
        ]

        for question in questions:
            self._test_question(question, "data_source_distinction")

    def _test_question(self, question, category, extra_data=None):
        """Test a single question and validate the response"""
        print(f"\nTesting: {question}")
        print("-" * 40)

        try:
            # Get GPT response
            context = self.service.get_context(question)
            messages = build_gpt_messages(context, [], question)
            response = get_conversation_response(messages, require_json=False)

            # Validate response
            validation_result = self._validate_response(
                question, response, category, extra_data
            )

            # Store result
            self.test_results.append(
                {
                    "question": question,
                    "category": category,
                    "response": response,
                    "validation": validation_result,
                    "extra_data": extra_data,
                }
            )

            # Print validation results
            if validation_result["issues"]:
                print(f"ISSUES FOUND: {len(validation_result['issues'])}")
                for issue in validation_result["issues"]:
                    print(f"   - {issue}")
            else:
                print("No issues found")

        except Exception as e:
            print(f"ERROR: {e}")
            self.test_results.append(
                {
                    "question": question,
                    "category": category,
                    "response": None,
                    "validation": {"error": str(e)},
                    "extra_data": extra_data,
                }
            )

    def _validate_response(self, question, response, category, extra_data):
        """Validate GPT response against database data"""
        validation_result = {
            "issues": [],
            "warnings": [],
            "data_accuracy": {},
            "source_accuracy": {},
        }

        # Extract numerical claims from response
        numerical_claims = self._extract_numerical_claims(response)

        # Validate each claim
        for claim in numerical_claims:
            if "miles" in claim.lower() or "mileage" in claim.lower():
                self._validate_mileage_claim(claim, validation_result, extra_data)
            elif "week" in claim.lower():
                self._validate_weekly_claim(claim, validation_result, extra_data)

        # Check data source usage
        self._validate_data_source_usage(response, category, validation_result)

        # Check for hallucination
        self._check_for_hallucination(response, validation_result)

        return validation_result

    def _extract_numerical_claims(self, response):
        """Extract numerical claims from GPT response"""
        # Look for patterns like "36 miles", "total of 42", etc.
        patterns = [
            r"(\d+(?:\.\d+)?)\s*miles?",
            r"total\s+of\s+(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*weekly",
            r"(\d+(?:\.\d+)?)\s*per\s+week",
        ]

        claims = []
        for pattern in patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                claims.append(f"{match} (from pattern: {pattern})")

        return claims

    def _validate_mileage_claim(self, claim, validation_result, extra_data):
        """Validate mileage claims against database"""
        if extra_data and "start_date" in extra_data:
            # Validate specific week mileage
            actual_mileage = self._get_actual_week_mileage(
                extra_data["start_date"], extra_data["end_date"]
            )

            # Extract claimed mileage from claim
            claimed_mileage = self._extract_number_from_claim(claim)

            if claimed_mileage and actual_mileage:
                if abs(claimed_mileage - actual_mileage) > 0.1:
                    validation_result["issues"].append(
                        f"Mileage discrepancy: GPT claims {claimed_mileage} miles, "
                        f"database has {actual_mileage} miles for {extra_data['week_name']}"
                    )
                else:
                    validation_result["data_accuracy"][claim] = "correct"

    def _get_actual_week_mileage(self, start_date, end_date):
        """Get actual mileage from database for a specific week"""
        try:
            result = self.session.execute(
                text(
                    """
                SELECT SUM(miles) as total_miles
                FROM plan_workouts
                WHERE date >= :start_date AND date <= :end_date
            """
                ),
                {"start_date": start_date, "end_date": end_date},
            ).fetchone()

            return result[0] if result and result[0] else 0
        except Exception as e:
            print(f"Error getting week mileage: {e}")
            return None

    def _extract_number_from_claim(self, claim):
        """Extract numerical value from a claim string"""
        numbers = re.findall(r"\d+(?:\.\d+)?", claim)
        return float(numbers[0]) if numbers else None

    def _validate_data_source_usage(self, response, category, validation_result):
        """Validate that GPT is using correct data sources"""
        if category == "plan_analysis":
            if "completed" in response.lower() and "planned" not in response.lower():
                validation_result["issues"].append(
                    "GPT may be using completed runs instead of planned runs for plan analysis"
                )
        elif category == "historical_analysis":
            if "planned" in response.lower() and "completed" not in response.lower():
                validation_result["issues"].append(
                    "GPT may be using planned runs instead of completed runs for historical analysis"
                )

    def _check_for_hallucination(self, response, validation_result):
        """Check for potential data hallucination"""
        # Look for specific patterns that might indicate hallucination
        if "january" in response.lower() and "2026" in response.lower():
            # Check if we actually have January 2026 data
            jan_data = self._get_actual_week_mileage("2026-01-01", "2026-01-31")
            if jan_data == 0:
                validation_result["issues"].append(
                    "GPT may be hallucinating January 2026 data that doesn't exist in database"
                )

    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE TEST REPORT")
        print("=" * 80)

        total_tests = len(self.test_results)
        failed_tests = sum(
            1 for result in self.test_results if result["validation"].get("issues")
        )
        error_tests = sum(
            1 for result in self.test_results if result["response"] is None
        )

        print(f"Total Tests: {total_tests}")
        print(f"Failed Tests: {failed_tests}")
        print(f"Error Tests: {error_tests}")
        print(
            f"Success Rate: {((total_tests - failed_tests - error_tests) / total_tests * 100):.1f}%"
        )

        # Category breakdown
        categories = {}
        for result in self.test_results:
            cat = result["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "failed": 0, "errors": 0}
            categories[cat]["total"] += 1
            if result["response"] is None:
                categories[cat]["errors"] += 1
            elif result["validation"].get("issues"):
                categories[cat]["failed"] += 1

        print("\nCategory Breakdown:")
        for cat, stats in categories.items():
            success_rate = (
                (stats["total"] - stats["failed"] - stats["errors"])
                / stats["total"]
                * 100
            )
            print(
                f"  {cat}: {success_rate:.1f}% success ({stats['total'] - stats['failed'] - stats['errors']}/{stats['total']})"
            )

        # Detailed issues
        print("\nDetailed Issues:")
        for result in self.test_results:
            if result["validation"].get("issues"):
                print(f"\nQuestion: {result['question']}")
                for issue in result["validation"]["issues"]:
                    print(f"  - {issue}")

        # Save detailed report
        self._save_detailed_report()

    def _save_detailed_report(self):
        """Save detailed test report to file"""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": self.user_id,
            "total_tests": len(self.test_results),
            "results": self.test_results,
        }

        with open("gpt_test_report.json", "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        print(f"\nDetailed report saved to: gpt_test_report.json")

    def close(self):
        """Clean up resources"""
        self.service.close()
        self.session.close()


def main():
    """Run the comprehensive test suite"""
    test_suite = GPTTestSuite()
    try:
        test_suite.run_all_tests()
    finally:
        test_suite.close()


if __name__ == "__main__":
    main()
