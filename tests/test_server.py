"""Tests for MCP server creation."""


from rs_cmw500_mcp.server import create_server


class TestServerCreation:
    """Test server creation."""

    def test_create_server(self):
        """Test that server can be created."""
        server = create_server()
        assert server is not None
        assert server.name == "rs-cmw500-mcp"
