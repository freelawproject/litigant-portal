"""
Pytest configuration and shared fixtures

This file is automatically discovered by pytest and provides
configuration and fixtures available to all tests.
"""

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database access for all tests.
    Remove this if you want explicit database access control.
    """
    pass


# Uncomment when you add Django REST Framework
# @pytest.fixture
# def api_client():
#     """
#     Example fixture for API testing with DRF.
#     Requires: pip install djangorestframework
#     """
#     from rest_framework.test import APIClient
#     return APIClient()


# Add more shared fixtures here as needed
