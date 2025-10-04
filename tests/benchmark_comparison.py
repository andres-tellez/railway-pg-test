"""
Performance benchmarking script for comparing old vs new functionality
Measures response times, error rates, and resource usage
"""

import time
import requests
import statistics
import json
from typing import Dict, List, Tuple
import concurrent.futures
from datetime import datetime


class PerformanceBenchmark:
    """Benchmark performance of API endpoints"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.results = {}

    def benchmark_endpoint(
        self,
        endpoint: str,
        method: str = "GET",
        data: Dict = None,
        headers: Dict = None,
        iterations: int = 10
    ) -> Dict:
        """Benchmark a single endpoint"""
        times = []
        errors = 0
        status_codes = []

        for i in range(iterations):
            try:
                start_time = time.time()

                if method.upper() == "GET":
                    response = requests.get(
                        f"{self.base_url}{endpoint}",
                        headers=headers or {},
                        timeout=30
                    )
                elif method.upper() == "POST":
                    response = requests.post(
                        f"{self.base_url}{endpoint}",
                        json=data or {},
                        headers=headers or {},
                        timeout=30
                    )

                end_time = time.time()
                response_time = end_time - start_time

                times.append(response_time)
                status_codes.append(response.status_code)

                if response.status_code >= 400:
                    errors += 1

            except Exception as e:
                errors += 1
                print(f"Error in iteration {i}: {e}")

        return {
            "endpoint": endpoint,
            "method": method,
            "iterations": iterations,
            "avg_response_time": statistics.mean(times) if times else 0,
            "min_response_time": min(times) if times else 0,
            "max_response_time": max(times) if times else 0,
            "median_response_time": statistics.median(times) if times else 0,
            "error_rate": (errors / iterations) * 100,
            "status_codes": status_codes,
            "successful_requests": iterations - errors
        }

    def benchmark_multiple_endpoints(
        self,
        endpoints: List[Tuple[str, str, Dict, Dict]],
        iterations: int = 10
    ) -> Dict:
        """Benchmark multiple endpoints concurrently"""
        results = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []

            for endpoint, method, data, headers in endpoints:
                future = executor.submit(
                    self.benchmark_endpoint,
                    endpoint, method, data, headers, iterations
                )
                futures.append((endpoint, future))

            for endpoint, future in futures:
                try:
                    results[endpoint] = future.result(timeout=300)
                except Exception as e:
                    results[endpoint] = {"error": str(e)}

        return results

    def compare_old_vs_new(self) -> Dict:
        """Compare performance between old and new implementations"""

        # Define endpoints to test
        endpoints = [
            ("/ask", "POST", {
                "question": "How am I doing this week?",
                "athlete_id": 123
            }, {"Content-Type": "application/json"}),

            ("/api/plan/current", "GET", None, {}),

            ("/api/plan/generate", "POST", {
                "race_date": "2025-12-01",
                "race_distance": "Marathon",
                "user_id": "123e4567-e89b-12d3-a456-426614174000"
            }, {"Content-Type": "application/json"}),

            ("/health", "GET", None, {}),

            ("/api/plan/debug/activities", "GET", None, {})
        ]

        print("🚀 Starting performance benchmark...")
        print(f"Testing {len(endpoints)} endpoints with 10 iterations each")
        print(f"Base URL: {self.base_url}")
        print("-" * 50)

        start_time = time.time()
        results = self.benchmark_multiple_endpoints(endpoints, iterations=10)
        end_time = time.time()

        total_time = end_time - start_time

        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_benchmark_time": total_time,
            "endpoints_tested": len(endpoints),
            "results": results,
            "summary": self._generate_summary(results)
        }

        return report

    def _generate_summary(self, results: Dict) -> Dict:
        """Generate summary statistics"""
        all_times = []
        total_errors = 0
        total_requests = 0

        for endpoint, data in results.items():
            if "error" not in data:
                all_times.append(data["avg_response_time"])
                total_errors += data["iterations"] - data["successful_requests"]
                total_requests += data["iterations"]

        return {
            "overall_avg_response_time": statistics.mean(all_times) if all_times else 0,
            "overall_error_rate": (total_errors / total_requests * 100) if total_requests > 0 else 0,
            "fastest_endpoint": min(results.items(),
                key=lambda x: x[1].get("avg_response_time", float('inf')))[0] if results else None,
            "slowest_endpoint": max(results.items(),
                key=lambda x: x[1].get("avg_response_time", 0))[0] if results else None
        }

    def print_report(self, report: Dict):
        """Print a formatted performance report"""
        print("\n" + "="*60)
        print("📊 PERFORMANCE BENCHMARK REPORT")
        print("="*60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Total Benchmark Time: {report['total_benchmark_time']:.2f}s")
        print(f"Endpoints Tested: {report['endpoints_tested']}")

        print("\n📈 SUMMARY STATISTICS:")
        summary = report['summary']
        print(f"Overall Average Response Time: {summary['overall_avg_response_time']:.3f}s")
        print(f"Overall Error Rate: {summary['overall_error_rate']:.1f}%")
        print(f"Fastest Endpoint: {summary['fastest_endpoint']}")
        print(f"Slowest Endpoint: {summary['slowest_endpoint']}")

        print("\n🔍 DETAILED RESULTS:")
        print("-" * 60)

        for endpoint, data in report['results'].items():
            if "error" in data:
                print(f"\n❌ {endpoint}: {data['error']}")
            else:
                print(f"\n✅ {endpoint}")
                print(f"   Method: {data['method']}")
                print(f"   Avg Response Time: {data['avg_response_time']:.3f}s")
                print(f"   Min/Max: {data['min_response_time']:.3f}s / {data['max_response_time']:.3f}s")
                print(f"   Error Rate: {data['error_rate']:.1f}%")
                print(f"   Successful Requests: {data['successful_requests']}/{data['iterations']}")

        print("\n" + "="*60)


def run_benchmark():
    """Run the performance benchmark"""
    benchmark = PerformanceBenchmark()

    try:
        report = benchmark.compare_old_vs_new()
        benchmark.print_report(report)

        # Save report to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_report_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n💾 Report saved to: {filename}")

    except Exception as e:
        print(f"❌ Benchmark failed: {e}")


if __name__ == "__main__":
    run_benchmark()
