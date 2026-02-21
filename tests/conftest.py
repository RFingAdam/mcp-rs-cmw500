"""Pytest configuration and fixtures."""

import asyncio
import os
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_scpi_socket():
    """Create mock SCPI socket."""
    socket = AsyncMock()
    socket.is_connected = True
    socket.address = "192.168.1.100:5025"

    # Default responses
    socket.query = AsyncMock(
        return_value="Rohde&Schwarz,CMW500,1234567,V3.8.10"
    )
    socket.send = AsyncMock()
    socket.wait_opc = AsyncMock(return_value=True)
    socket.query_float_list = AsyncMock(return_value=[1e9, 1.5e9, 2e9])

    return socket


@pytest.fixture
def cmw_test_config():
    """Get CMW500 test configuration from environment."""
    return {
        "host": os.environ.get("CMW_TEST_HOST", "127.0.0.1"),
        "port": int(os.environ.get("CMW_TEST_PORT", "5025")),
    }


@pytest.fixture
def skip_without_cmw(cmw_test_config):
    """Skip test if no CMW500 available."""
    if not os.environ.get("CMW_TEST_HOST"):
        pytest.skip("CMW_TEST_HOST not set, skipping integration test")
