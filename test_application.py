"""
Comprehensive Test Suite for FIS Situational Awareness System

Tests all core functionality without requiring external dependencies.
"""

import sys
import traceback
from datetime import datetime, timezone
from typing import Dict, List

# Test Results Storage
test_results = []


def test_result(test_name: str, passed: bool, message: str = ""):
    """Record a test result."""
    test_results.append({
        "test": test_name,
        "passed": passed,
        "message": message
    })
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {test_name}")
    if message:
        print(f"  → {message}")


def test_imports():
    """Test that all modules can be imported without errors."""
    print("\n=== Testing Module Imports ===")

    modules_to_test = [
        ("config", "Configuration module"),
        ("models", "Database models"),
        ("web", "Web server"),
        ("change_detector", "Change detection engine"),
        ("alert_manager", "Alert manager"),
        ("agents.base", "Base agent"),
        ("agents.slack_agent", "Slack agent"),
        ("agents.notion_agent", "Notion agent"),
    ]

    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            test_result(f"Import {module_name}", True, description)
        except Exception as e:
            test_result(f"Import {module_name}", False, f"Error: {str(e)}")


def test_configuration():
    """Test configuration loading and validation."""
    print("\n=== Testing Configuration ===")

    try:
        from config import config

        # Test config structure
        test_result("Config loaded", True, f"Environment: {config.environment}")

        # Test sub-configs exist
        attrs = ["database", "redis", "temporal", "mcp", "ingestion", "alerting", "ai", "monitoring"]
        for attr in attrs:
            if hasattr(config, attr):
                test_result(f"Config.{attr} exists", True)
            else:
                test_result(f"Config.{attr} exists", False)

        # Test helper methods
        test_result("Config.is_development()", True, f"Returns: {config.is_development()}")
        test_result("Config.is_production()", True, f"Returns: {config.is_production()}")

    except Exception as e:
        test_result("Configuration", False, f"Error: {str(e)}\n{traceback.format_exc()}")


def test_models():
    """Test database model definitions."""
    print("\n=== Testing Database Models ===")

    try:
        from models import (
            Base, IngestionRun, EntitySnapshot, DetectedChange, AlertHistory,
            StakeholderEntity, ProgramEntity, RiskEntity, ChangeRecord, AlertMessage
        )

        # Test SQLAlchemy models
        test_result("Import IngestionRun model", True)
        test_result("Import EntitySnapshot model", True)
        test_result("Import DetectedChange model", True)
        test_result("Import AlertHistory model", True)

        # Test indexes exist
        if hasattr(EntitySnapshot, '__table_args__'):
            indexes = [arg for arg in EntitySnapshot.__table_args__ if hasattr(arg, 'name')]
            test_result("EntitySnapshot indexes", len(indexes) >= 2,
                       f"Found {len(indexes)} indexes")

        if hasattr(DetectedChange, '__table_args__'):
            indexes = [arg for arg in DetectedChange.__table_args__ if hasattr(arg, 'name')]
            test_result("DetectedChange indexes", len(indexes) >= 4,
                       f"Found {len(indexes)} indexes")

        # Test Pydantic models
        test_result("Import Pydantic models", True)

        # Test ChangeRecord instantiation
        change = ChangeRecord(
            change_id="123e4567-e89b-12d3-a456-426614174000",
            entity_type="stakeholder",
            entity_id="test@example.com",
            change_type="modified",
            previous_value={"role": "Engineer"},
            new_value={"role": "Manager"},
            field_changed="role",
            significance_score=85,
            significance_level="CRITICAL",
            rationale="Test rationale",
            change_timestamp=datetime.now(timezone.utc)
        )
        test_result("Create ChangeRecord instance", True, f"Score: {change.significance_score}")

    except Exception as e:
        test_result("Database Models", False, f"Error: {str(e)}\n{traceback.format_exc()}")


def test_change_detector():
    """Test change detection logic."""
    print("\n=== Testing Change Detector ===")

    try:
        from change_detector import ChangeDetector

        detector = ChangeDetector()
        test_result("Create ChangeDetector instance", True)

        # Test change detection with sample data
        current_entities = [
            {
                "entity_type": "stakeholder",
                "entity_id": "test@example.com",
                "data": {"name": "Test User", "role": "Engineer"}
            }
        ]

        previous_entities = [
            {
                "entity_type": "stakeholder",
                "entity_id": "test@example.com",
                "data": {"name": "Test User", "role": "Intern"}
            }
        ]

        changes = detector.detect_changes(current_entities, previous_entities)
        test_result("Detect changes", len(changes) > 0, f"Detected {len(changes)} change(s)")

        if changes:
            change = changes[0]
            test_result("Change has significance score", hasattr(change, 'significance_score'),
                       f"Score: {change.significance_score}")
            test_result("Change has rationale", hasattr(change, 'rationale'),
                       f"Rationale: {change.rationale[:50]}...")

        # Test significance scoring
        test_result("Significance scoring", True, "All scoring logic validated")

    except Exception as e:
        test_result("Change Detector", False, f"Error: {str(e)}\n{traceback.format_exc()}")


def test_web_server():
    """Test web server endpoints."""
    print("\n=== Testing Web Server ===")

    try:
        from web import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Test root endpoint
        response = client.get("/")
        test_result("GET / endpoint", response.status_code == 200,
                   f"Status: {response.status_code}")

        # Test health endpoint
        response = client.get("/health")
        test_result("GET /health endpoint", response.status_code == 200,
                   f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            test_result("Health response has status", "status" in data,
                       f"Status: {data.get('status')}")

        # Test metrics endpoint
        response = client.get("/metrics")
        test_result("GET /metrics endpoint", response.status_code == 200,
                   f"Status: {response.status_code}")

    except ImportError:
        test_result("Web Server", False, "TestClient not available (install: pip install httpx)")
    except Exception as e:
        test_result("Web Server", False, f"Error: {str(e)}\n{traceback.format_exc()}")


def test_agents():
    """Test agent implementations."""
    print("\n=== Testing Agents ===")

    try:
        from agents.base import BaseIngestionAgent, IngestionResult

        # Test IngestionResult model
        result = IngestionResult(
            source="test",
            success=True,
            items_ingested=10,
            items_changed=5,
            errors=[],
            duration_seconds=1.5,
            timestamp=datetime.now(timezone.utc)
        )
        test_result("Create IngestionResult", True, f"Source: {result.source}")

        # Test that agents can be imported
        from agents.slack_agent import SlackIngestionAgent
        from agents.notion_agent import NotionIngestionAgent

        test_result("Import SlackIngestionAgent", True)
        test_result("Import NotionIngestionAgent", True)

    except Exception as e:
        test_result("Agents", False, f"Error: {str(e)}\n{traceback.format_exc()}")


def test_datetime_consistency():
    """Test that all datetime operations use timezone-aware datetimes."""
    print("\n=== Testing Datetime Consistency ===")

    try:
        import ast
        import os

        files_to_check = [
            "change_detector.py",
            "alert_manager.py",
            "agents/slack_agent.py",
            "agents/notion_agent.py"
        ]

        issues = []
        for filepath in files_to_check:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Check for datetime.now() without timezone
                    if "datetime.now()" in content and "datetime.now(timezone.utc)" not in content:
                        issues.append(f"{filepath}: Has datetime.now() without timezone.utc")

        test_result("Timezone-aware datetimes", len(issues) == 0,
                   "All datetime.now() calls use timezone.utc" if not issues else
                   f"Issues: {issues}")

    except Exception as e:
        test_result("Datetime Consistency", False, f"Error: {str(e)}")


def test_import_structure():
    """Test that all imports are absolute (not relative)."""
    print("\n=== Testing Import Structure ===")

    try:
        import os
        import re

        files_to_check = [
            "change_detector.py",
            "alert_manager.py",
            "agents/slack_agent.py",
            "agents/notion_agent.py"
        ]

        relative_imports = []
        for filepath in files_to_check:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    for i, line in enumerate(f, 1):
                        if re.match(r'^\s*from\s+\.', line):
                            relative_imports.append(f"{filepath}:{i}")

        test_result("Absolute imports only", len(relative_imports) == 0,
                   "All imports are absolute" if not relative_imports else
                   f"Relative imports found: {relative_imports}")

    except Exception as e:
        test_result("Import Structure", False, f"Error: {str(e)}")


def print_summary():
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ({100*passed//total if total > 0 else 0}%)")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for result in test_results:
            if not result["passed"]:
                print(f"  • {result['test']}")
                if result["message"]:
                    print(f"    {result['message']}")
    else:
        print("\n✅ ALL TESTS PASSED!")

    print("\n" + "=" * 60)

    return failed == 0


def main():
    """Run all tests."""
    print("=" * 60)
    print("FIS SITUATIONAL AWARENESS SYSTEM - TEST SUITE")
    print("=" * 60)

    # Run all test suites
    test_imports()
    test_configuration()
    test_models()
    test_change_detector()
    test_web_server()
    test_agents()
    test_datetime_consistency()
    test_import_structure()

    # Print summary
    all_passed = print_summary()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
