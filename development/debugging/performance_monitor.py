#!/usr/bin/env python3
"""
Performance monitoring and optimization for AWS discovery system
Provides real-time monitoring, bottleneck detection, and optimization suggestions
"""

import sys
import os
import time
import psutil
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

# Add the inventag package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

try:
    from inventag.discovery.optimized_discovery import OptimizedAWSDiscovery
    import boto3
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class PerformanceMonitor:
    """Real-time performance monitoring for AWS discovery"""

    def __init__(self):
        # Initialize with minimal setup for testing
        self.session = boto3.Session()
        self.discovery = OptimizedAWSDiscovery(session=self.session)

        # Performance tracking
        self.service_times = defaultdict(list)
        self.operation_times = defaultdict(list)
        self.resource_counts = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.memory_usage = deque(maxlen=100)
        self.cpu_usage = deque(maxlen=100)

        # Monitoring state
        self.monitoring = False
        self.monitor_thread = None

    def start_monitoring(self):
        """Start system resource monitoring"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_system_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("📊 Performance monitoring started")

    def stop_monitoring(self):
        """Stop system resource monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        print("📊 Performance monitoring stopped")

    def _monitor_system_resources(self):
        """Monitor system CPU and memory usage"""
        while self.monitoring:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()

                self.cpu_usage.append(cpu_percent)
                self.memory_usage.append(memory_info.percent)

                time.sleep(1)
            except Exception as e:
                print(f"⚠️  System monitoring error: {e}")
                break

    def benchmark_service(self, service_name, iterations=3):
        """Benchmark a specific service discovery"""
        print(f"\n🏃 Benchmarking {service_name.upper()} service ({iterations} iterations)...")

        times = []
        resource_counts = []

        for i in range(iterations):
            print(f"  🔄 Iteration {i+1}/{iterations}...")

            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

            try:
                resources = self.discovery.discover_service(service_name)

                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

                duration = end_time - start_time
                memory_delta = end_memory - start_memory

                times.append(duration)
                resource_counts.append(len(resources))

                print(f"    ⏱️  Time: {duration:.2f}s")
                print(f"    📊 Resources: {len(resources)}")
                print(f"    💾 Memory: {memory_delta:+.1f} MB")

            except Exception as e:
                print(f"    ❌ Error: {e}")
                self.error_counts[service_name] += 1

        if times:
            avg_time = sum(times) / len(times)
            avg_resources = sum(resource_counts) / len(resource_counts)

            self.service_times[service_name].extend(times)
            self.resource_counts[service_name].extend(resource_counts)

            print(f"  📈 Average time: {avg_time:.2f}s")
            print(f"  📈 Average resources: {avg_resources:.0f}")
            print(f"  📈 Resources/second: {avg_resources/avg_time:.1f}")

            return {
                "service": service_name,
                "avg_time": avg_time,
                "avg_resources": avg_resources,
                "throughput": avg_resources / avg_time,
                "times": times,
                "resource_counts": resource_counts,
            }

        return None

    def benchmark_all_services(self):
        """Benchmark all major AWS services"""
        print("\n🚀 Comprehensive Service Benchmarking")
        print("=" * 50)

        services = [
            "s3",
            "ec2",
            "iam",
            "lambda",
            "cloudfront",
            "route53",
            "rds",
            "cloudwatch",
            "logs",
        ]

        self.start_monitoring()

        results = {}
        total_start = time.time()

        for service in services:
            try:
                result = self.benchmark_service(service, iterations=2)
                if result:
                    results[service] = result
            except KeyboardInterrupt:
                print("\n⚠️  Benchmarking interrupted by user")
                break
            except Exception as e:
                print(f"❌ Failed to benchmark {service}: {e}")

        total_time = time.time() - total_start
        self.stop_monitoring()

        # Generate benchmark report
        self._generate_benchmark_report(results, total_time)

        return results

    def _generate_benchmark_report(self, results, total_time):
        """Generate comprehensive benchmark report"""
        print("\n" + "=" * 60)
        print("📋 PERFORMANCE BENCHMARK REPORT")
        print("=" * 60)

        if not results:
            print("❌ No benchmark results to report")
            return

        # Sort by throughput (resources per second)
        sorted_results = sorted(results.items(), key=lambda x: x[1]["throughput"], reverse=True)

        print(f"🎯 Service Performance Ranking:")
        for i, (service, data) in enumerate(sorted_results, 1):
            print(
                f"  {i:2d}. {service.upper():12s} - {data['throughput']:6.1f} resources/sec ({data['avg_time']:.2f}s avg)"
            )

        # Performance categories
        fast_services = [s for s, d in results.items() if d["avg_time"] < 2.0]
        slow_services = [s for s, d in results.items() if d["avg_time"] > 10.0]

        print(f"\n⚡ Fast Services (< 2s): {', '.join(fast_services) if fast_services else 'None'}")
        print(f"🐌 Slow Services (> 10s): {', '.join(slow_services) if slow_services else 'None'}")

        # Resource discovery stats
        total_resources = sum(d["avg_resources"] for d in results.values())
        print(f"\n📊 Discovery Statistics:")
        print(f"  📈 Total resources discovered: {total_resources:.0f}")
        print(f"  ⏱️  Total benchmark time: {total_time:.1f}s")
        print(f"  🎯 Overall throughput: {total_resources/total_time:.1f} resources/sec")

        # System resource usage
        if self.cpu_usage and self.memory_usage:
            avg_cpu = sum(self.cpu_usage) / len(self.cpu_usage)
            max_cpu = max(self.cpu_usage)
            avg_memory = sum(self.memory_usage) / len(self.memory_usage)
            max_memory = max(self.memory_usage)

            print(f"\n💻 System Resource Usage:")
            print(f"  🖥️  CPU: {avg_cpu:.1f}% avg, {max_cpu:.1f}% peak")
            print(f"  💾 Memory: {avg_memory:.1f}% avg, {max_memory:.1f}% peak")

        # Optimization recommendations
        self._generate_optimization_recommendations(results)

    def _generate_optimization_recommendations(self, results):
        """Generate optimization recommendations based on benchmark results"""
        print(f"\n🔧 OPTIMIZATION RECOMMENDATIONS:")

        recommendations = []

        # Identify slow services
        slow_services = [s for s, d in results.items() if d["avg_time"] > 5.0]
        if slow_services:
            recommendations.append(f"🐌 Optimize slow services: {', '.join(slow_services)}")
            recommendations.append("   - Consider parallel processing for these services")
            recommendations.append("   - Review API call patterns and add caching")

        # Check for high resource count services
        high_resource_services = [s for s, d in results.items() if d["avg_resources"] > 50]
        if high_resource_services:
            recommendations.append(
                f"📊 High resource count services: {', '.join(high_resource_services)}"
            )
            recommendations.append("   - Consider pagination optimization")
            recommendations.append("   - Implement resource filtering at API level")

        # Check for low throughput
        low_throughput_services = [s for s, d in results.items() if d["throughput"] < 5.0]
        if low_throughput_services:
            recommendations.append(
                f"⚡ Low throughput services: {', '.join(low_throughput_services)}"
            )
            recommendations.append("   - Review API call efficiency")
            recommendations.append("   - Consider batch operations where possible")

        # System resource recommendations
        if self.cpu_usage and max(self.cpu_usage) > 80:
            recommendations.append(
                "🖥️  High CPU usage detected - consider reducing parallel workers"
            )

        if self.memory_usage and max(self.memory_usage) > 80:
            recommendations.append("💾 High memory usage detected - implement resource streaming")

        # Error rate recommendations
        error_services = [s for s, count in self.error_counts.items() if count > 0]
        if error_services:
            recommendations.append(f"❌ Services with errors: {', '.join(error_services)}")
            recommendations.append("   - Review error handling and retry logic")

        if recommendations:
            for rec in recommendations:
                print(f"  {rec}")
        else:
            print("  ✅ No specific optimizations needed - performance looks good!")

    def profile_memory_usage(self, service_name):
        """Profile memory usage for a specific service"""
        print(f"\n🧠 Memory Profiling for {service_name.upper()}")
        print("-" * 40)

        import tracemalloc

        tracemalloc.start()

        # Baseline memory
        baseline = psutil.Process().memory_info().rss / 1024 / 1024
        print(f"📊 Baseline memory: {baseline:.1f} MB")

        # Run discovery
        start_time = time.time()
        resources = self.discovery.discover_service(service_name)
        end_time = time.time()

        # Final memory
        final = psutil.Process().memory_info().rss / 1024 / 1024
        delta = final - baseline

        print(f"📊 Final memory: {final:.1f} MB")
        print(f"📊 Memory delta: {delta:+.1f} MB")
        print(f"📊 Resources found: {len(resources)}")
        print(f"📊 Memory per resource: {delta/len(resources):.3f} MB" if resources else "N/A")
        print(f"⏱️  Discovery time: {end_time - start_time:.2f}s")

        # Get top memory allocations
        current, peak = tracemalloc.get_traced_memory()
        print(f"📊 Peak traced memory: {peak / 1024 / 1024:.1f} MB")

        tracemalloc.stop()

        return {
            "service": service_name,
            "baseline_mb": baseline,
            "final_mb": final,
            "delta_mb": delta,
            "resources": len(resources),
            "memory_per_resource": delta / len(resources) if resources else 0,
            "discovery_time": end_time - start_time,
            "peak_traced_mb": peak / 1024 / 1024,
        }

    def continuous_monitoring(self, duration_minutes=10):
        """Run continuous monitoring for a specified duration"""
        print(f"\n📊 Starting {duration_minutes}-minute continuous monitoring...")

        self.start_monitoring()

        end_time = time.time() + (duration_minutes * 60)
        services = ["s3", "ec2", "iam", "lambda"]

        iteration = 0
        while time.time() < end_time:
            iteration += 1
            print(f"\n🔄 Monitoring iteration {iteration}")

            for service in services:
                try:
                    start = time.time()
                    resources = self.discovery.discover_service(service)
                    duration = time.time() - start

                    self.service_times[service].append(duration)
                    self.resource_counts[service].append(len(resources))

                    print(f"  {service}: {len(resources)} resources in {duration:.2f}s")

                except Exception as e:
                    print(f"  {service}: Error - {e}")
                    self.error_counts[service] += 1

            # Wait before next iteration
            time.sleep(30)

        self.stop_monitoring()

        # Generate continuous monitoring report
        self._generate_continuous_report(duration_minutes)

    def _generate_continuous_report(self, duration_minutes):
        """Generate report for continuous monitoring"""
        print(f"\n📋 CONTINUOUS MONITORING REPORT ({duration_minutes} minutes)")
        print("=" * 60)

        for service, times in self.service_times.items():
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)

                counts = self.resource_counts[service]
                avg_resources = sum(counts) / len(counts) if counts else 0

                print(f"📊 {service.upper()}:")
                print(f"  ⏱️  Time: {avg_time:.2f}s avg ({min_time:.2f}s - {max_time:.2f}s)")
                print(f"  📈 Resources: {avg_resources:.0f} avg")
                print(f"  🔄 Iterations: {len(times)}")

                if service in self.error_counts and self.error_counts[service] > 0:
                    print(f"  ❌ Errors: {self.error_counts[service]}")

    def save_performance_data(self, filename=None):
        """Save performance data to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_data_{timestamp}.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "service_times": {k: list(v) for k, v in self.service_times.items()},
            "resource_counts": {k: list(v) for k, v in self.resource_counts.items()},
            "error_counts": dict(self.error_counts),
            "cpu_usage": list(self.cpu_usage),
            "memory_usage": list(self.memory_usage),
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"💾 Performance data saved to: {filename}")
        return filename


def main():
    """Main function for performance monitoring"""
    print("⚡ AWS Discovery Performance Monitor")
    print("=" * 40)

    monitor = PerformanceMonitor()

    try:
        # Quick benchmark of key services
        print("\n1️⃣  Quick Service Benchmark")
        key_services = ["s3", "ec2", "iam"]

        for service in key_services:
            monitor.benchmark_service(service, iterations=1)

        print("\n2️⃣  Memory Profiling")
        monitor.profile_memory_usage("s3")

        print("\n3️⃣  Full Benchmark (optional)")
        response = input("Run full benchmark? (y/N): ").lower().strip()

        if response == "y":
            monitor.benchmark_all_services()

        # Save performance data
        monitor.save_performance_data()

    except KeyboardInterrupt:
        print("\n⚠️  Monitoring interrupted by user")
    except Exception as e:
        print(f"\n❌ Monitoring failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
