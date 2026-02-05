"""
Test script for Weekly Executive Digest generation.

Validates digest logic without requiring full infrastructure.
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock


def test_digest_generator_import():
    """Test that digest generator can be imported."""
    print("Testing digest_generator import...")
    try:
        from digest_generator import DigestGenerator
        print("✓ DigestGenerator imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import DigestGenerator: {e}")
        return False


def test_digest_structure():
    """Test digest structure and formatting."""
    print("\nTesting digest structure...")

    try:
        from digest_generator import DigestGenerator

        # Create mock database session
        mock_db = MagicMock()
        mock_mcp = MagicMock()

        # Create generator
        generator = DigestGenerator(mock_db, mock_mcp)

        # Test account snapshot generation
        print("  Testing account snapshot generation...")
        snapshot = generator._generate_account_snapshot([])

        assert "status" in snapshot, "Missing 'status' field"
        assert "momentum" in snapshot, "Missing 'momentum' field"
        assert "summary" in snapshot, "Missing 'summary' field"
        assert snapshot["status"] in ["Green", "Yellow", "Red"], f"Invalid status: {snapshot['status']}"
        assert snapshot["momentum"] in ["Improving", "Flat", "Deteriorating"], f"Invalid momentum: {snapshot['momentum']}"

        print(f"    ✓ Account snapshot: {snapshot['status']} | {snapshot['momentum']}")

        # Test what changed generation
        print("  Testing what changed generation...")
        changes = generator._generate_what_changed([])
        assert isinstance(changes, list), "What changed should return a list"
        print(f"    ✓ What changed: {len(changes)} items")

        # Test key risks generation
        print("  Testing key risks generation...")
        risks = generator._generate_key_risks([])
        assert isinstance(risks, list), "Key risks should return a list"
        assert len(risks) <= 3, "Should return at most 3 risks"
        print(f"    ✓ Key risks: {len(risks)} items")

        # Test opportunities generation
        print("  Testing opportunities generation...")
        opportunities = generator._generate_opportunities([], [])
        assert isinstance(opportunities, list), "Opportunities should return a list"
        assert len(opportunities) <= 3, "Should return at most 3 opportunities"
        print(f"    ✓ Opportunities: {len(opportunities)} items")

        # Test decisions needed generation
        print("  Testing decisions needed generation...")
        decisions = generator._generate_decisions_needed([])
        assert isinstance(decisions, list), "Decisions should return a list"
        print(f"    ✓ Decisions: {len(decisions)} items")

        # Test external signals generation
        print("  Testing external signals generation...")
        signals = generator._generate_external_signals([])
        assert isinstance(signals, str), "External signals should return a string"
        print(f"    ✓ External signals: {len(signals)} chars")

        # Test full digest formatting
        print("  Testing full digest formatting...")
        digest = generator._format_digest(
            account_snapshot=snapshot,
            what_changed=["Test change 1", "Test change 2"],
            key_risks=[],
            opportunities=[],
            decisions_needed=[],
            external_signals="No external signals this week."
        )

        # Validate structure
        assert "FIS WEEKLY EXECUTIVE DIGEST" in digest, "Missing header"
        assert "Account Snapshot:" in digest, "Missing account snapshot section"
        assert "What Changed:" in digest, "Missing what changed section"
        assert "Key Risks:" in digest, "Missing key risks section"
        assert "Actions Needed:" in digest, "Missing actions needed section"
        assert "External Signals:" in digest, "Missing external signals section"

        # Validate word count
        word_count = len(digest.split())
        print(f"    ✓ Digest generated: {word_count} words")

        if word_count > 250:
            print(f"    ⚠ Warning: Digest exceeds 250 words ({word_count} words)")
        else:
            print(f"    ✓ Word count within limit (≤250 words)")

        print("\n✓ All digest structure tests passed")
        return True

    except Exception as e:
        print(f"✗ Digest structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_significance_scoring():
    """Test significance scoring for different change types."""
    print("\nTesting significance scoring logic...")

    try:
        from digest_generator import DigestGenerator
        from models import DetectedChange

        # Create mock database session
        mock_db = MagicMock()
        mock_mcp = MagicMock()

        # Create generator
        generator = DigestGenerator(mock_db, mock_mcp)

        # Test account snapshot with critical changes
        print("  Testing with CRITICAL changes...")
        mock_changes = []
        for i in range(3):
            change = Mock()
            change.significance_level = "CRITICAL"
            change.significance_score = 80 + i
            change.entity_type = "stakeholder"
            change.change_type = "added"
            change.new_value = {"name": f"Test Person {i}", "role": "CEO"}
            change.previous_value = None
            change.field_changed = None
            mock_changes.append(change)

        snapshot = generator._generate_account_snapshot(mock_changes)
        assert snapshot["status"] == "Red", f"Expected Red status with 3 critical changes, got {snapshot['status']}"
        print(f"    ✓ Status correctly calculated as Red with 3 CRITICAL changes")

        # Test with HIGH changes
        print("  Testing with HIGH changes...")
        mock_changes = []
        for i in range(5):
            change = Mock()
            change.significance_level = "HIGH"
            change.significance_score = 65 + i
            change.entity_type = "program"
            change.change_type = "modified"
            change.new_value = {"status": "At Risk"}
            change.previous_value = {"status": "On Track"}
            change.field_changed = "status"
            mock_changes.append(change)

        snapshot = generator._generate_account_snapshot(mock_changes)
        assert snapshot["status"] == "Yellow", f"Expected Yellow status with 5 HIGH changes, got {snapshot['status']}"
        print(f"    ✓ Status correctly calculated as Yellow with 5 HIGH changes")

        # Test with no significant changes
        print("  Testing with no significant changes...")
        snapshot = generator._generate_account_snapshot([])
        assert snapshot["status"] == "Green", f"Expected Green status with no changes, got {snapshot['status']}"
        print(f"    ✓ Status correctly calculated as Green with no changes")

        print("\n✓ All significance scoring tests passed")
        return True

    except Exception as e:
        print(f"✗ Significance scoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_registration():
    """Test that workflow is properly registered."""
    print("\nTesting workflow registration...")

    try:
        from workflows import WeeklyDigestWorkflow
        print("  ✓ WeeklyDigestWorkflow imported successfully")

        # Check that workflow has run method
        assert hasattr(WeeklyDigestWorkflow, 'run'), "WeeklyDigestWorkflow missing run method"
        print("  ✓ WeeklyDigestWorkflow has run method")

        print("\n✓ Workflow registration test passed")
        return True

    except Exception as e:
        print(f"✗ Workflow registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_activity_registration():
    """Test that activity is properly registered."""
    print("\nTesting activity registration...")

    try:
        from activities import generate_weekly_digest
        print("  ✓ generate_weekly_digest activity imported successfully")

        # Check that activity is callable
        assert callable(generate_weekly_digest), "generate_weekly_digest is not callable"
        print("  ✓ generate_weekly_digest is callable")

        print("\n✓ Activity registration test passed")
        return True

    except Exception as e:
        print(f"✗ Activity registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all digest tests."""
    print("=" * 60)
    print("FIS WEEKLY DIGEST - TEST SUITE")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Import Test", test_digest_generator_import()))
    results.append(("Structure Test", test_digest_structure()))
    results.append(("Significance Scoring Test", test_significance_scoring()))
    results.append(("Workflow Registration Test", test_workflow_registration()))
    results.append(("Activity Registration Test", test_activity_registration()))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed ({int(passed/total*100)}%)")

    if passed == total:
        print("\n✓ All tests passed! Weekly digest is ready to use.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
