"""
Tests for the Litigant Portal.

Tests custom application logic only - not Django built-ins.
"""

from django.core.management import call_command
from django.test import TestCase


class DjangoSystemTests(TestCase):
    """Verify Django configuration is correct."""

    def test_system_checks_pass(self):
        """Django system checks should pass without warnings."""
        # This catches misconfigurations early
        call_command("check", "--fail-level", "WARNING")
