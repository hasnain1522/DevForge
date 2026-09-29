"""Regression tests for test-coverage mission target normalization."""

from devforge.agents.mission_builder import MissionBuilderAgent


def test_test_coverage_targets_are_created_under_tests():
    assert MissionBuilderAgent._test_targets(
        ["app.py", "database.py", "main.py"]
    ) == [
        "tests/test_app.py",
        "tests/test_database.py",
        "tests/test_main.py",
    ]
