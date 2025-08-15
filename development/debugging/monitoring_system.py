#!/usr/bin/env python3
"""
Comprehensive monitoring and alerting system for AWS discovery
Provides real-time monitoring, alerting, and automated optimization
"""

import sys
import os
import time
import json
import threading
import smtplib
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

# Email imports with fallback
try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart

    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Add the inventag package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

try:
    from inventag.discovery.optimized_discovery import OptimizedAWSDiscovery
    import boto3
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class DiscoveryMonitor:
    """Comprehensive monitoring system for AWS discovery"""

    def __init__(self, config=None):
        self.session = boto3.Session()
        self.discovery = OptimizedAWSDiscovery(session=self.session)

        # Monitoring configuration
        self.config = config or {
            "monitoring_interval": 300,  # 5 minutes
            "alert_thresholds": {
                "discovery_time": 60,  # seconds
                "error_rate": 0.1,  # 10%
                "resource_change_rate": 0.2,  # 20%
                "memory_usage": 80,  # percent
                "cpu_usage": 80,  # percent
            },
            "email_alerts": {
                "enabled": False,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "recipients": [],
            },
            "services_to_monitor": ["s3", "ec2", "iam", "lambda", "rds"],
        }

        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread = None

        # Historical data
        self.discovery_history = deque(maxlen=100)
        self.performance_history = deque(maxlen=100)
        self.error_history = deque(maxlen=100)
        self.resource_counts = defaultdict(deque)

        # Alerts
        self.active_alerts = []
        self.alert_history = deque(maxlen=50)

        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Create console handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def start_monitoring(self):
        """Start continuous monitoring"""

        if self.monitoring_active:
            self.logger.warning("Monitoring is already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        self.logger.info("🚀 Discovery monitoring started")
        print("🚀 Discovery monitoring started")
        print(f"📊 Monitoring interval: {self.config['monitoring_interval']} seconds")
        print(f"🎯 Services: {', '.join(self.config['services_to_monitor'])}")

    def stop_monitoring(self):
        """Stop continuous monitoring"""

        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        self.logger.info("⏹️  Discovery monitoring stopped")
        print("⏹️  Discovery monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""

        while self.monitoring_active:
            try:
                # Run discovery cycle
                cycle_start = time.time()
                cycle_data = self._run_discovery_cycle()
                cycle_duration = time.time() - cycle_start

                # Store historical data
                self.discovery_history.append(cycle_data)
                self.performance_history.append(
                    {
                        "timestamp": datetime.now(),
                        "duration": cycle_duration,
                        "total_resources": cycle_data["total_resources"],
                        "services_discovered": len(cycle_data["services"]),
                        "errors": cycle_data["errors"],
                    }
                )

                # Check for alerts
                self._check_alerts(cycle_data, cycle_duration)

                # Log cycle summary
                self.logger.info(
                    f"Discovery cycle complete: {cycle_data['total_resources']} resources in {cycle_duration:.2f}s"
                )

                # Wait for next cycle
                time.sleep(self.config["monitoring_interval"])

            except Exception as e:
                self.logger.error(f"Monitoring cycle failed: {e}")
                self.error_history.append(
                    {
                        "timestamp": datetime.now(),
                        "error": str(e),
                        "type": "monitoring_cycle",
                    }
                )
                time.sleep(30)  # Shorter wait on error

    def _run_discovery_cycle(self):
        """Run a single discovery cycle"""

        cycle_data = {
            "timestamp": datetime.now(),
            "services": {},
            "total_resources": 0,
            "errors": 0,
            "warnings": 0,
        }

        for service in self.config["services_to_monitor"]:
            try:
                service_start = time.time()
                resources = self.discovery.discover_service(service)
                service_duration = time.time() - service_start

                service_data = {
                    "resource_count": len(resources),
                    "duration": service_duration,
                    "status": "success",
                }

                cycle_data["services"][service] = service_data
                cycle_data["total_resources"] += len(resources)

                # Store resource count history
                self.resource_counts[service].append(
                    {"timestamp": datetime.now(), "count": len(resources)}
                )

            except Exception as e:
                self.logger.warning(f"Service {service} discovery failed: {e}")
                cycle_data["services"][service] = {
                    "resource_count": 0,
                    "duration": 0,
                    "status": "error",
                    "error": str(e),
                }
                cycle_data["errors"] += 1

        return cycle_data

    def _check_alerts(self, cycle_data, cycle_duration):
        """Check for alert conditions"""

        alerts_triggered = []

        # Check discovery time threshold
        if cycle_duration > self.config["alert_thresholds"]["discovery_time"]:
            alerts_triggered.append(
                {
                    "type": "performance",
                    "severity": "warning",
                    "message": f"Discovery cycle took {cycle_duration:.2f}s (threshold: {self.config['alert_thresholds']['discovery_time']}s)",
                    "timestamp": datetime.now(),
                }
            )

        # Check error rate
        total_services = len(self.config["services_to_monitor"])
        error_rate = cycle_data["errors"] / total_services if total_services > 0 else 0

        if error_rate > self.config["alert_thresholds"]["error_rate"]:
            alerts_triggered.append(
                {
                    "type": "reliability",
                    "severity": "critical",
                    "message": f"High error rate: {error_rate:.1%} ({cycle_data['errors']}/{total_services} services failed)",
                    "timestamp": datetime.now(),
                }
            )

        # Check resource count changes
        self._check_resource_change_alerts(alerts_triggered)

        # Process alerts
        for alert in alerts_triggered:
            self._process_alert(alert)

    def _check_resource_change_alerts(self, alerts_triggered):
        """Check for significant resource count changes"""

        for service, history in self.resource_counts.items():
            if len(history) < 2:
                continue

            current_count = history[-1]["count"]
            previous_count = history[-2]["count"]

            if previous_count == 0:
                continue

            change_rate = abs(current_count - previous_count) / previous_count

            if change_rate > self.config["alert_thresholds"]["resource_change_rate"]:
                alerts_triggered.append(
                    {
                        "type": "resource_change",
                        "severity": "warning",
                        "message": f"{service.upper()} resource count changed significantly: {previous_count} → {current_count} ({change_rate:.1%} change)",
                        "timestamp": datetime.now(),
                    }
                )

    def _process_alert(self, alert):
        """Process and handle an alert"""

        # Add to active alerts
        self.active_alerts.append(alert)
        self.alert_history.append(alert)

        # Log alert
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        emoji = severity_emoji.get(alert["severity"], "📢")

        self.logger.warning(f"{emoji} ALERT [{alert['type'].upper()}]: {alert['message']}")
        print(f"{emoji} ALERT [{alert['type'].upper()}]: {alert['message']}")

        # Send email alert if configured
        if self.config["email_alerts"]["enabled"]:
            self._send_email_alert(alert)

        # Auto-remediation for certain alert types
        self._attempt_auto_remediation(alert)

    def _send_email_alert(self, alert):
        """Send email alert"""

        if not EMAIL_AVAILABLE:
            self.logger.warning("Email functionality not available - skipping email alert")
            return

        try:
            msg = MimeMultipart()
            msg["From"] = self.config["email_alerts"]["username"]
            msg["To"] = ", ".join(self.config["email_alerts"]["recipients"])
            msg["Subject"] = f"AWS Discovery Alert - {alert['type'].title()}"

            body = f"""
AWS Discovery Monitoring Alert

Type: {alert['type']}
Severity: {alert['severity']}
Time: {alert['timestamp']}
Message: {alert['message']}

This is an automated alert from the AWS Discovery monitoring system.
            """

            msg.attach(MimeText(body, "plain"))

            server = smtplib.SMTP(
                self.config["email_alerts"]["smtp_server"],
                self.config["email_alerts"]["smtp_port"],
            )
            server.starttls()
            server.login(
                self.config["email_alerts"]["username"],
                self.config["email_alerts"]["password"],
            )

            text = msg.as_string()
            server.sendmail(
                self.config["email_alerts"]["username"],
                self.config["email_alerts"]["recipients"],
                text,
            )
            server.quit()

            self.logger.info("📧 Email alert sent successfully")

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")

    def _attempt_auto_remediation(self, alert):
        """Attempt automatic remediation for certain alert types"""

        if alert["type"] == "performance" and alert["severity"] == "warning":
            # For performance issues, try reducing parallel workers
            if hasattr(self.discovery, "max_workers") and self.discovery.max_workers > 1:
                self.discovery.max_workers = max(1, self.discovery.max_workers - 1)
                self.logger.info(
                    f"🔧 Auto-remediation: Reduced parallel workers to {self.discovery.max_workers}"
                )

        elif alert["type"] == "reliability" and alert["severity"] == "critical":
            # For reliability issues, enable fallback mechanisms
            if hasattr(self.discovery, "fallback_to_all_regions"):
                self.discovery.fallback_to_all_regions = True
                self.logger.info("🔧 Auto-remediation: Enabled region fallback")

    def get_monitoring_status(self):
        """Get current monitoring status"""

        if not self.discovery_history:
            return {"status": "no_data", "message": "No monitoring data available"}

        latest_cycle = self.discovery_history[-1]
        latest_performance = self.performance_history[-1] if self.performance_history else None

        # Calculate averages over last 10 cycles
        recent_cycles = list(self.performance_history)[-10:]

        if recent_cycles:
            avg_duration = sum(c["duration"] for c in recent_cycles) / len(recent_cycles)
            avg_resources = sum(c["total_resources"] for c in recent_cycles) / len(recent_cycles)
            total_errors = sum(c["errors"] for c in recent_cycles)
        else:
            avg_duration = 0
            avg_resources = 0
            total_errors = 0

        status = {
            "monitoring_active": self.monitoring_active,
            "last_cycle": latest_cycle["timestamp"].isoformat(),
            "total_resources": latest_cycle["total_resources"],
            "services_status": latest_cycle["services"],
            "performance": {
                "avg_duration": avg_duration,
                "avg_resources": avg_resources,
                "total_errors": total_errors,
            },
            "active_alerts": len(self.active_alerts),
            "alert_history": len(self.alert_history),
        }

        return status

    def generate_monitoring_report(self):
        """Generate comprehensive monitoring report"""

        print("\n📋 AWS DISCOVERY MONITORING REPORT")
        print("=" * 50)

        status = self.get_monitoring_status()

        print(f"🔄 Monitoring Status: {'Active' if status['monitoring_active'] else 'Inactive'}")
        print(f"📅 Last Cycle: {status['last_cycle']}")
        print(f"📊 Total Resources: {status['total_resources']}")

        print(f"\n📈 Performance Metrics (Last 10 cycles):")
        print(f"  ⏱️  Average Duration: {status['performance']['avg_duration']:.2f}s")
        print(f"  📊 Average Resources: {status['performance']['avg_resources']:.0f}")
        print(f"  ❌ Total Errors: {status['performance']['total_errors']}")

        print(f"\n🎯 Service Status:")
        for service, data in status["services_status"].items():
            status_emoji = "✅" if data["status"] == "success" else "❌"
            print(
                f"  {status_emoji} {service.upper()}: {data['resource_count']} resources ({data['duration']:.2f}s)"
            )

        print(f"\n🚨 Alerts:")
        print(f"  📢 Active Alerts: {status['active_alerts']}")
        print(f"  📜 Alert History: {status['alert_history']}")

        if self.active_alerts:
            print(f"\n  Recent Active Alerts:")
            for alert in self.active_alerts[-5:]:  # Show last 5
                severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
                emoji = severity_emoji.get(alert["severity"], "📢")
                print(f"    {emoji} {alert['type']}: {alert['message']}")

        # Resource trend analysis
        print(f"\n📈 Resource Trends:")
        for service in self.config["services_to_monitor"]:
            if service in self.resource_counts and len(self.resource_counts[service]) >= 2:
                history = list(self.resource_counts[service])
                current = history[-1]["count"]
                previous = history[-2]["count"]
                change = current - previous

                trend_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                print(f"  {trend_emoji} {service.upper()}: {current} ({change:+d})")

        return status

    def save_monitoring_data(self, filename=None):
        """Save monitoring data to file"""

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monitoring_data_{timestamp}.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "discovery_history": [
                {
                    "timestamp": d["timestamp"].isoformat(),
                    "services": d["services"],
                    "total_resources": d["total_resources"],
                    "errors": d["errors"],
                }
                for d in self.discovery_history
            ],
            "performance_history": [
                {
                    "timestamp": p["timestamp"].isoformat(),
                    "duration": p["duration"],
                    "total_resources": p["total_resources"],
                    "services_discovered": p["services_discovered"],
                    "errors": p["errors"],
                }
                for p in self.performance_history
            ],
            "alert_history": [
                {
                    "timestamp": a["timestamp"].isoformat(),
                    "type": a["type"],
                    "severity": a["severity"],
                    "message": a["message"],
                }
                for a in self.alert_history
            ],
            "resource_counts": {
                service: [
                    {"timestamp": r["timestamp"].isoformat(), "count": r["count"]} for r in history
                ]
                for service, history in self.resource_counts.items()
            },
        }

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        print(f"💾 Monitoring data saved to: {filename}")
        return filename


def main():
    """Main function for monitoring system"""

    print("📊 AWS Discovery Monitoring System")
    print("=" * 40)

    # Example configuration
    config = {
        "monitoring_interval": 60,  # 1 minute for demo
        "alert_thresholds": {
            "discovery_time": 30,
            "error_rate": 0.1,
            "resource_change_rate": 0.3,
            "memory_usage": 80,
            "cpu_usage": 80,
        },
        "email_alerts": {"enabled": False},  # Disable for demo
        "services_to_monitor": ["s3", "ec2", "iam"],
    }

    monitor = DiscoveryMonitor(config)

    try:
        print("\n1️⃣  Starting monitoring (will run for 5 minutes)...")
        monitor.start_monitoring()

        # Let it run for a few cycles
        time.sleep(300)  # 5 minutes

        print("\n2️⃣  Stopping monitoring...")
        monitor.stop_monitoring()

        print("\n3️⃣  Generating report...")
        monitor.generate_monitoring_report()

        print("\n4️⃣  Saving data...")
        monitor.save_monitoring_data()

    except KeyboardInterrupt:
        print("\n⚠️  Monitoring interrupted by user")
        monitor.stop_monitoring()
    except Exception as e:
        print(f"\n❌ Monitoring failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
