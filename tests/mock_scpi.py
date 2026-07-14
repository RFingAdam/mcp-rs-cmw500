"""Mock SCPI transport for hardware-free driver/tool tests.

`MockSCPISocket` is a drop-in replacement for `SCPISocket` that records every
command emitted by the driver and returns scripted responses. It lets us assert
the exact SCPI strings a driver method produces and feed canned query responses
(including sequences, for polling loops) without any instrument.

Usage:
    from tests.mock_scpi import MockSCPISocket, make_mock_driver

    cmw = make_mock_driver({"FETC:INT:LTE:SIGN1:EBL:PCC:REL?": "0,1,1,3,100"})
    await cmw.lte_ebl_init()
    assert "INITiate:LTE:SIGN1:EBL" in cmw._scpi.writes
"""

from collections.abc import Callable
from typing import Any

from rs_cmw500_mcp.driver.cmw500_driver import CMW500Driver

Response = str | list[str] | Callable[[str], str]


class MockSCPISocket:
    """In-memory SCPI transport that records commands and replays responses.

    Args:
        responses: Maps a command (or a distinctive substring of one) to a
            response. A value may be a plain string, a list of strings replayed
            in order (last value repeats once exhausted), or a callable taking
            the full command and returning a string.
        default_response: Returned when no key matches (default ``"0"``).
    """

    def __init__(
        self,
        responses: dict[str, Response] | None = None,
        default_response: str = "0",
    ) -> None:
        self.responses: dict[str, Response] = dict(responses or {})
        self.default_response = default_response
        self.commands: list[str] = []  # every send + query, in order
        self.writes: list[str] = []  # send() only (non-query writes)
        self.queries: list[str] = []  # query() only
        self.is_connected = True
        self.address = "mock:5025"

    # -- transport surface used by CMW500Driver ---------------------------------

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def send(self, command: str) -> None:
        self.commands.append(command)
        self.writes.append(command)

    async def read_response(self, timeout: float | None = None) -> str:
        return self.default_response

    async def query(self, command: str, timeout: float | None = None) -> str:
        self.commands.append(command)
        self.queries.append(command)
        return self._lookup(command)

    async def query_float_list(self, command: str, timeout: float | None = None) -> list[float]:
        response = await self.query(command, timeout)
        if not response:
            return []
        return [float(x) for x in response.split(",")]

    async def wait_opc(self, timeout: float | None = None) -> bool:
        self.commands.append("*OPC?")
        self.queries.append("*OPC?")
        resp = self._lookup("*OPC?")
        return resp.strip() == "1" if resp else True

    # -- helpers ----------------------------------------------------------------

    def _lookup(self, command: str) -> str:
        value: Response | None = None
        if command in self.responses:
            value = self.responses[command]
        else:
            for key, val in self.responses.items():
                if key in command:
                    value = val
                    break
        if value is None:
            # *OPC? has a sensible default even when unscripted.
            return "1" if command.strip() == "*OPC?" else self.default_response
        if callable(value):
            return value(command)
        if isinstance(value, list):
            if not value:
                return self.default_response
            return value[0] if len(value) == 1 else value.pop(0)
        return value

    def assert_sent(self, fragment: str) -> None:
        """Assert some emitted command contains ``fragment``."""
        assert any(fragment in c for c in self.commands), (
            f"Expected a command containing {fragment!r}; got {self.commands}"
        )

    def last_write(self) -> str:
        return self.writes[-1]


def make_mock_driver(
    responses: dict[str, Response] | None = None,
    default_response: str = "0",
    **kwargs: Any,
) -> CMW500Driver:
    """Build a CMW500Driver backed by a MockSCPISocket (no hardware)."""
    driver = CMW500Driver(host="mock", port=5025, **kwargs)
    driver._scpi = MockSCPISocket(responses, default_response)  # type: ignore[assignment]
    return driver
