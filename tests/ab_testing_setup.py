"""
A/B Testing setup for comparing old vs new functionality
Allows gradual rollout and comparison of different implementations
"""

import os
import random
from typing import Dict, Any
from flask import request, g
from functools import wraps


class ABTestingManager:
    """Manages A/B testing for different feature implementations"""

    def __init__(self):
        self.tests = {}
        self.results = {}

    def register_test(
        self,
        test_name: str,
        variants: Dict[str, Any],
        traffic_split: Dict[str, float] = None,
    ):
        """Register a new A/B test"""
        if traffic_split is None:
            # Default to 50/50 split
            traffic_split = {
                variant: 1.0 / len(variants) for variant in variants.keys()
            }

        self.tests[test_name] = {"variants": variants, "traffic_split": traffic_split}

        print(f"✅ Registered A/B test: {test_name}")
        print(f"   Variants: {list(variants.keys())}")
        print(f"   Traffic Split: {traffic_split}")

    def get_variant(self, test_name: str, user_id: str = None) -> str:
        """Get the variant for a specific user and test"""
        if test_name not in self.tests:
            return "default"

        # Use user_id for consistent assignment, or generate random
        if user_id:
            # Use hash for consistent assignment
            hash_value = hash(f"{test_name}_{user_id}")
            random.seed(hash_value)

        rand = random.random()
        cumulative = 0

        for variant, split in self.tests[test_name]["traffic_split"].items():
            cumulative += split
            if rand <= cumulative:
                return variant

        return list(self.tests[test_name]["variants"].keys())[0]

    def record_result(self, test_name: str, variant: str, metric: str, value: Any):
        """Record a result for analysis"""
        if test_name not in self.results:
            self.results[test_name] = {}

        if variant not in self.results[test_name]:
            self.results[test_name][variant] = {}

        if metric not in self.results[test_name][variant]:
            self.results[test_name][variant][metric] = []

        self.results[test_name][variant][metric].append(value)

    def get_results(self, test_name: str) -> Dict:
        """Get results for a specific test"""
        return self.results.get(test_name, {})


# Global A/B testing manager
ab_manager = ABTestingManager()


def ab_test(
    test_name: str, variants: Dict[str, Any], traffic_split: Dict[str, float] = None
):
    """Decorator for A/B testing different implementations"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get user ID from request context
            user_id = getattr(g, "user_id", None) or request.headers.get("X-User-Id")

            # Register test if not already registered
            if test_name not in ab_manager.tests:
                ab_manager.register_test(test_name, variants, traffic_split)

            # Get variant for this user
            variant = ab_manager.get_variant(test_name, str(user_id))

            # Record the variant assignment
            ab_manager.record_result(
                test_name,
                variant,
                "assignment",
                {
                    "user_id": user_id,
                    "timestamp": request.headers.get("X-Request-ID", "unknown"),
                    "endpoint": request.endpoint,
                },
            )

            # Execute the appropriate variant
            start_time = time.time()

            try:
                if variant in variants:
                    result = variants[variant](*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Record success metrics
                end_time = time.time()
                ab_manager.record_result(
                    test_name, variant, "response_time", end_time - start_time
                )
                ab_manager.record_result(test_name, variant, "success", True)

                return result

            except Exception as e:
                # Record error metrics
                ab_manager.record_result(test_name, variant, "success", False)
                ab_manager.record_result(test_name, variant, "error", str(e))
                raise

        return wrapper

    return decorator


def generate_ab_report():
    """Generate A/B testing report"""
    print("\n" + "=" * 60)
    print("📊 A/B TESTING REPORT")
    print("=" * 60)

    for test_name, test_data in ab_manager.tests.items():
        print(f"\n🧪 Test: {test_name}")
        print(f"   Variants: {list(test_data['variants'].keys())}")
        print(f"   Traffic Split: {test_data['traffic_split']}")

        if test_name in ab_manager.results:
            results = ab_manager.results[test_name]
            print(f"   Results:")

            for variant, metrics in results.items():
                print(f"     {variant}:")

                if "response_time" in metrics:
                    avg_time = sum(metrics["response_time"]) / len(
                        metrics["response_time"]
                    )
                    print(f"       Avg Response Time: {avg_time:.3f}s")

                if "success" in metrics:
                    success_rate = (
                        sum(metrics["success"]) / len(metrics["success"]) * 100
                    )
                    print(f"       Success Rate: {success_rate:.1f}%")

                if "assignment" in metrics:
                    print(f"       Total Assignments: {len(metrics['assignment'])}")

        print("-" * 40)

    print("=" * 60)


if __name__ == "__main__":
    generate_ab_report()
