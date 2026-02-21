"""Tests for SCPI socket transport."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rs_cmw500_mcp.driver.scpi_socket import SCPISocket
from rs_cmw500_mcp.exceptions import (
    ConnectionError,
)


class TestSCPISocketInit:
    """Test SCPISocket initialization."""

    def test_defaults(self):
        socket = SCPISocket()
        assert socket.host == "127.0.0.1"
        assert socket.port == 5025
        assert socket.timeout == 5.0
        assert socket.command_timeout == 30.0
        assert socket.is_connected is False

    def test_custom_params(self):
        socket = SCPISocket(
            host="192.168.1.100",
            port=5026,
            timeout=10.0,
            command_timeout=60.0,
        )
        assert socket.host == "192.168.1.100"
        assert socket.port == 5026

    def test_address_property(self):
        socket = SCPISocket(host="10.0.0.1", port=5025)
        assert socket.address == "10.0.0.1:5025"


class TestSCPISocketConnection:
    """Test SCPISocket connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        socket = SCPISocket()
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.wait_for", return_value=(mock_reader, mock_writer)):
            await socket.connect()

        assert socket.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test connection timeout."""
        socket = SCPISocket(timeout=0.1)

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            with pytest.raises(ConnectionError, match="timed out"):
                await socket.connect()

    @pytest.mark.asyncio
    async def test_connect_refused(self):
        """Test connection refused."""
        socket = SCPISocket()

        with patch("asyncio.wait_for", side_effect=OSError("Connection refused")):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await socket.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        socket = SCPISocket()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        socket._writer = mock_writer
        socket._reader = AsyncMock()
        socket._connected = True

        await socket.disconnect()
        assert socket.is_connected is False

    @pytest.mark.asyncio
    async def test_already_connected(self):
        """Test connecting when already connected does nothing."""
        socket = SCPISocket()
        socket._connected = True
        socket._writer = MagicMock()

        # Should return without error
        await socket.connect()


class TestSCPISocketCommunication:
    """Test SCPI socket communication."""

    @pytest.fixture
    def connected_socket(self):
        """Create a connected socket with mocked internals."""
        socket = SCPISocket()
        socket._connected = True
        socket._writer = MagicMock()
        socket._writer.write = MagicMock()
        socket._writer.drain = AsyncMock()
        socket._reader = AsyncMock()
        return socket

    @pytest.mark.asyncio
    async def test_send(self, connected_socket):
        """Test sending a command."""
        await connected_socket.send("*RST")
        connected_socket._writer.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_not_connected(self):
        """Test send when not connected."""
        socket = SCPISocket()
        with pytest.raises(ConnectionError, match="Not connected"):
            await socket.send("*RST")

    @pytest.mark.asyncio
    async def test_query(self, connected_socket):
        """Test query."""
        connected_socket._reader.readline = AsyncMock(return_value=b"Rohde&Schwarz,CMW500\n")

        async def mock_wait_for(coro, **kw):
            return await coro

        with patch("asyncio.wait_for", side_effect=mock_wait_for):
            response = await connected_socket.query("*IDN?")
        assert "Rohde&Schwarz" in response

    @pytest.mark.asyncio
    async def test_query_float_list(self, connected_socket):
        """Test float list query."""
        connected_socket._reader.readline = AsyncMock(return_value=b"1.0,2.0,3.0\n")

        async def mock_wait_for(coro, **kw):
            return await coro

        with patch("asyncio.wait_for", side_effect=mock_wait_for):
            values = await connected_socket.query_float_list("TEST?")
        assert values == [1.0, 2.0, 3.0]

    @pytest.mark.asyncio
    async def test_wait_opc(self, connected_socket):
        """Test OPC wait."""
        connected_socket._reader.readline = AsyncMock(return_value=b"1\n")

        async def mock_wait_for(coro, **kw):
            return await coro

        with patch("asyncio.wait_for", side_effect=mock_wait_for):
            result = await connected_socket.wait_opc()
        assert result is True

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        socket = SCPISocket()
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.wait_for", return_value=(mock_reader, mock_writer)):
            async with socket as s:
                assert s.is_connected is True
            assert s.is_connected is False
