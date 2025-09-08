"""
pytest configuration file for GraSP tests.

This file configures pytest to handle asyncio properly.
"""

import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an instance of the default event loop for each test session.
    
    This ensures that there is always an event loop available for asyncio operations
    even when tests aren't explicitly async.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_asyncio_event_loop():
    """
    Ensure that all tests have access to an event loop.
    
    This fixture is automatically applied to all tests and ensures that 
    an event loop is available in the MainThread, which fixes the
    "RuntimeError: There is no current event loop in thread 'MainThread'" error.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield
    # Don't close the loop as it might be needed for other tests
